"""Live check of the Intelligence Hub back end on a fresh throwaway shop: metrics by period and category, the rules and their alerts,
My tasks, acknowledging, and AI Replenish suggestions with an order or dismiss decision. Uses only the local PesoWeb.

    python scripts/hub_check.py
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import agent_service                   # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso.verticals import ProductSpec           # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    run = "hub-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Hub Check Store", "Demo", "Owner", f"{run}@hub.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pid = drv.add_product(a, ProductSpec("HUB-1", "Test item", "Grocery", 60, 100, False), cat, basics)
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)

    print("1. Metrics by period and category")
    m = drv._call("GET", "/api/ai/hub/metrics?period=7d", a.token)
    row = m["branches"][0]
    check(m["period"] == "7d" and m["companyName"] == "Hub Check Store" and len(m["branches"]) == 1, "the 7-day overview is for this company's branch")
    check(all(k in row for k in ("sales", "cogs", "marginPct", "inventoryValue", "turnover", "daysOfStock", "shrinkage", "shrinkagePct", "expiryAtRisk")), "each branch carries margin, turnover, days of stock and shrinkage")
    cats = drv._call("GET", "/api/ai/hub/categories", a.token)
    check(any(c["name"] == "Grocery" for c in cats), "the category picker lists the company's categories")
    byc = drv._call("GET", f"/api/ai/hub/metrics?period=today&categoryId={cat}", a.token)
    check(byc["categoryId"] == cat, "a category can be chosen")
    st, _ = drv._call("GET", "/api/ai/hub/metrics?period=decade", a.token, raw=True)
    check(st == 400, "an unknown period is refused")

    print("2. Rules, alerts and My tasks")
    rules = drv._call("GET", "/api/ai/hub/rules", a.token)
    check(len(rules) == 8 and all(r["enabled"] for r in rules), "eight rules, all on by default")
    st, _ = drv._call("PUT", "/api/ai/hub/rules/Shrinkage", a.token, json_body={"enabled": True, "threshold": 2, "role": "Janitor", "severity": "Act", "notifyEmail": False}, raw=True)
    check(st == 400, "a rule with an unknown role is refused")
    st, _ = drv._call("PUT", "/api/ai/hub/rules/Nope", a.token, json_body={"enabled": True, "threshold": 2, "role": "Owner", "severity": "Act", "notifyEmail": False}, raw=True)
    check(st == 400, "an unknown rule is refused")
    drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 103, "Source": "Ai", "Confidence": "learned"}, raw=True)
    drv._call("PUT", "/api/ai/hub/rules/ApprovalsWaiting", a.token, json_body={"enabled": True, "threshold": 0, "role": "Pricing manager", "severity": "Act", "notifyEmail": False})
    tasks = drv._call("GET", "/api/ai/hub/tasks", a.token)
    kinds = sorted({t["kind"] for t in tasks["items"]})
    check("Approval" in kinds and "Alert" in kinds, "the owner's tasks hold the waiting proposal and the rule's alert")
    alert = next(t for t in tasks["items"] if t["kind"] == "Alert" and "waiting" in t["title"].lower())
    check(alert["role"] == "Pricing manager" and alert["severity"] == "Act" and alert["branch"] == "Whole company", "the alert names its role, severity and scope")
    st, _ = drv._call("POST", f"/api/ai/hub/alerts/{alert['id']}/ack", a.token, raw=True)
    after = drv._call("GET", "/api/ai/hub/tasks", a.token)
    check(st == 200 and next(t for t in after["items"] if t["key"] == alert["key"])["acknowledged"], "an alert can be acknowledged")
    counts = drv._call("GET", "/api/ai/hub/notifications", a.token)
    check(counts["total"] >= 2 and counts["act"] >= 1, "the notification count includes them")
    pending = drv.list_price_changes(a, status="PendingApproval")
    drv.reject_list_price(a, pending[0]["id"], "check done")
    final = drv._call("GET", "/api/ai/hub/tasks", a.token)
    check(not any(t["kind"] == "Alert" and "waiting" in t["title"].lower() for t in final["items"]), "the alert closes by itself once the proposal is decided")
    drv._call("PUT", "/api/ai/hub/rules/ApprovalsWaiting", a.token, json_body={"enabled": False, "threshold": 10, "role": "Pricing manager", "severity": "Watch", "notifyEmail": False})
    check(drv.hub_evaluate(a).get("open") is not None, "the agent runner can ask PesoWeb to check the rules")

    print("3. AI Replenish")
    item = {"WarehouseId": wh, "ProductId": pid, "OnHand": 3, "RatePerDay": 4, "DaysOfCover": 0.8, "ReorderPoint": 8, "SuggestedQty": 33, "UnitCost": 60,
            "LeadTimeDays": 2, "CoverDays": 7, "Confidence": "learned", "Reason": "3 on hand covers 0.8 days at about 4 a day"}
    st, body = drv.post_replenish(a, [wh], [item])
    check(st == 200 and body["added"] == 1, "the agent posts a reorder suggestion")
    st, body = drv.post_replenish(a, [wh], [{**item, "SuggestedQty": 40}])
    open_ = drv.replenish_suggestions(a)
    check(len(open_) == 1 and open_[0]["suggestedQty"] == 40 and open_[0]["cost"] == 2400, "a newer run replaces the open suggestion for that branch")
    t = drv._call("GET", "/api/ai/hub/tasks", a.token)
    r = next(x for x in t["items"] if x["kind"] == "Reorder")
    check(r["severity"] == "Act" and "Test item" in r["title"], "it shows in My tasks, urgent because the stock runs out before the delivery")
    st, _ = drv.decide_replenish(a, open_[0]["id"], "Ordered")
    check(st == 200 and not drv.replenish_suggestions(a) and len(drv.replenish_suggestions(a, "Ordered")) == 1, "marking it Ordered closes it")
    st, _ = drv.decide_replenish(a, open_[0]["id"], "Dismissed")
    check(st == 400, "a decided suggestion cannot be decided again")
    drv._call("PUT", "/api/ai/control/Replenish", a.token, json_body={"enabled": False})
    st, body = drv.post_replenish(a, [wh], [item])
    check(st == 422 and body.get("code") == "AI_FEATURE_OFF", "with AI Replenish switched off, PesoWeb refuses new suggestions")
    drv._call("PUT", "/api/ai/control/Replenish", a.token, json_body={"enabled": True})
    st, o = drv._call("POST", "/api/ai/control/run/Replenish", a.token, raw=True)
    check(st == 202, "AI Replenish can be run from AI Control")
    ran = []
    runner = agent_service.AgentRunner(drv, a, {"Replenish": lambda: ran.append(1) or "0 reorder suggestions"}, log=lambda *_: None)
    out = runner.poll_once()
    check(ran == [1] and out and out[0]["outcome"] == "done", "the agent runner picks it up")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

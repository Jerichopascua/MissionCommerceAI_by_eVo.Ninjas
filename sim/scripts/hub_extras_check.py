"""Live check of the later hub features on a fresh throwaway shop: regions and targets, a named assignee, the notification channel,
competitor prices, AI Customer Mission, and draft purchase orders from reorders. Uses only the local PesoWeb.

    python scripts/hub_extras_check.py
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso.verticals import ProductSpec           # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    run = "hx-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Hub Extras Store", "Demo", "Owner", f"{run}@hx.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pid = drv.add_product(a, ProductSpec("HX-1", "Test item", "Grocery", 60, 100, False), cat, basics)
    sup = drv.add_supplier(a, "Hub Supplier", 1)
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)

    print("1. Regions and targets")
    st, _ = drv._call("PUT", f"/api/ai/branch-settings/{wh}", a.token, json_body={"PricingEnabled": True, "Region": "Metro", "SalesTargetPerDay": 5000, "WasteTargetPct": 2.5}, raw=True)
    b = drv._call("GET", "/api/ai/branch-settings", a.token)[0]
    check(st == 200 and b["region"] == "Metro" and b["salesTargetPerDay"] == 5000 and b["wasteTargetPct"] == 2.5, "a branch's region and targets are saved and listed")
    m = drv._call("GET", "/api/ai/hub/metrics?period=today", a.token)
    row = m["branches"][0]
    check(row["region"] == "Metro" and row["salesTarget"] is not None and [r["region"] for r in m["regions"]] == ["Metro"], "the overview groups the branch by region and carries its target")
    mr = drv._call("GET", "/api/ai/hub/metrics?period=today&region=Nowhere", a.token)
    check(mr["branches"] == [] and mr["region"] == "Nowhere", "a region with no branches shows nothing")
    st, _ = drv._call("PUT", f"/api/ai/branch-settings/{wh}", a.token, json_body={"PricingEnabled": True, "WasteTargetPct": 150}, raw=True)
    check(st == 400, "a waste target above 100 percent is refused")

    print("2. A named assignee")
    people = drv._call("GET", "/api/ai/hub/assignees", a.token)
    me = next(p for p in people if p["email"] == f"{run}@hx.test")
    drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 103, "Source": "Ai", "Confidence": "learned"}, raw=True)
    st, _ = drv._call("PUT", "/api/ai/hub/rules/ApprovalsWaiting", a.token, json_body={"enabled": True, "threshold": 0, "role": "Pricing manager", "severity": "Act", "notifyEmail": False, "assigneeUserId": 99999999}, raw=True)
    check(st == 400, "a rule cannot be assigned to someone who is not a user of the company")
    st, _ = drv._call("PUT", "/api/ai/hub/rules/ApprovalsWaiting", a.token, json_body={"enabled": True, "threshold": 0, "role": "Pricing manager", "severity": "Act", "notifyEmail": False, "assigneeUserId": me["id"]}, raw=True)
    tasks = drv._call("GET", "/api/ai/hub/tasks", a.token)
    alert = next((t for t in tasks["items"] if t["kind"] == "Alert"), None)
    check(st == 200 and alert and alert["assignee"] == me["name"] and alert["assignedToMe"], "the alert carries the named person and shows as assigned to them")

    print("3. Notification channel")
    st, o = drv._call("PUT", "/api/ai/channel", a.token, json_body={"WebhookUrl": "http://10.0.0.5/hook", "SendAlerts": True, "SendPriceChanges": False}, raw=True)
    check(st == 400, "an address on a private network is refused")
    st, o = drv._call("PUT", "/api/ai/channel", a.token, json_body={"WebhookUrl": "https://user:pw@hooks.example.com/x", "SendAlerts": True, "SendPriceChanges": False}, raw=True)
    check(st == 400, "an address with a user name and password in it is refused")
    st, o = drv._call("PUT", "/api/ai/channel", a.token, json_body={"WebhookUrl": "https://hooks.example.com/x", "SendAlerts": True, "SendPriceChanges": True}, raw=True)
    check(st == 200 and o["configured"] and o["sendPriceChanges"], "a public https address is saved")
    st, o = drv._call("PUT", "/api/ai/channel", a.token, json_body={"WebhookUrl": "", "SendAlerts": True, "SendPriceChanges": False}, raw=True)
    check(st == 200 and not o["configured"], "the address can be cleared")

    print("4. Competitor prices")
    st, o = drv._call("PUT", "/api/ai/competitor-prices", a.token, json_body={"Items": [{"ProductId": pid, "Competitor": "Rival A", "Price": 90}, {"ProductId": pid, "Competitor": "Rival B", "Price": 99}]}, raw=True)
    check(st == 200 and o["saved"] == 2, "a person can enter rival prices")
    st, o = drv.post_competitor_prices(a, [{"ProductId": pid, "Competitor": "Rival C", "Price": 104}, {"ProductId": 999999, "Competitor": "Nobody", "Price": 5}])
    check(st == 200 and o["saved"] == 1, "an agent can feed rival prices; an unknown product is ignored")
    summary = drv._call("GET", "/api/ai/competitor-summary", a.token)
    check(len(summary) == 1 and summary[0]["lowest"] == 90 and summary[0]["count"] == 3, "the advisor can read the lowest rival price per product")
    q = drv._call("GET", "/api/Pricing/Approvals", a.token)
    item = q["items"][0]
    rival = next((c for c in item["checks"] if c["text"].startswith("Competitors")), None)
    check(item["competitorCount"] == 3 and rival and not rival["ok"], "the Approval Center shows the rivals next to the proposal and flags a raise 5% above the lowest")

    print("5. AI Customer Mission")
    row = {"WarehouseId": wh, "Mission": "Quick top-up", "Baskets": 60, "SharePct": 60, "AvgItems": 2, "AvgValue": 90, "PeakHour": 18, "Insight": "Most visits are one or two items.", "WindowDays": 14}
    st, o = drv.post_missions(a, [wh], [row, {**row, "Mission": "Weekly restock", "Baskets": 40, "SharePct": 40}])
    got = drv.missions(a)
    check(st == 200 and o["added"] == 2 and len(got) == 2 and got[0]["mission"] == "Quick top-up", "the agent posts the mission picture and it is listed biggest first")
    drv._call("PUT", "/api/ai/control/CustomerMission", a.token, json_body={"enabled": False})
    st, o = drv.post_missions(a, [wh], [row])
    check(st == 422 and o.get("code") == "AI_FEATURE_OFF", "with AI Customer Mission switched off, PesoWeb refuses a new picture")
    drv._call("PUT", "/api/ai/control/CustomerMission", a.token, json_body={"enabled": True})

    print("6. Draft purchase order from a reorder")
    item = {"WarehouseId": wh, "ProductId": pid, "OnHand": 3, "RatePerDay": 4, "DaysOfCover": 0.8, "ReorderPoint": 8, "SuggestedQty": 33, "UnitCost": 60,
            "LeadTimeDays": 2, "CoverDays": 7, "Confidence": "learned", "Reason": "short"}
    drv.post_replenish(a, [wh], [item])
    sug = drv.replenish_suggestions(a)[0]
    st, o = drv._call("POST", "/api/ai/replenish/draft-order", a.token, json_body={"Ids": [sug["id"]]}, raw=True)
    order = (o.get("orders") or [None])[0]
    check(st == 200 and order and order["lines"] == 1 and order["total"] == 1980 and order["supplier"] == "Hub Supplier", "a reorder becomes a draft purchase order with the company's supplier")
    pur = drv._call("GET", f"/api/Purchases/PurchaseDetail/{order['purchaseId']}", a.token, raw=True) if order else (0, {})
    done = drv.replenish_suggestions(a, "Ordered")
    check(len(done) == 1 and done[0]["purchaseId"] == order["purchaseId"] and not drv.replenish_suggestions(a), "the suggestion is marked Ordered and linked to the purchase")
    stock = drv._call("GET", f"/api/Inventory/ProductDetail/{pid}?warehouse={wh}", a.token)
    qty = float((stock.get("product") or stock).get("quantity") or 0)
    check(qty == 0, "a Pending purchase order adds no stock")
    st, _ = drv._call("POST", "/api/ai/replenish/draft-order", a.token, json_body={"Ids": [sug["id"]]}, raw=True)
    check(st == 400, "an already-ordered suggestion cannot be ordered again")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Live check of the expiry side of AI Product Loss Prevention on a fresh throwaway shop: a batch that will not sell before it expires is listed
with the amount at risk and a discount, a markdown is proposed through PesoWeb's rules into the Approval Center, a repeat run does not propose
it again, it is a task for the store manager, and without pricing rules nothing is proposed.

    python scripts/expiry_risk_check.py
"""
import datetime as dt
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso import agent_service                   # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso.verticals import ProductSpec           # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    run = "ex-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Expiry Risk Store", "Demo", "Owner", f"{run}@ex.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Dairy")
    sup = drv.add_supplier(a, "Dairy Supplier", 1)
    pid = drv.add_product(a, ProductSpec("EX-1", "Fresh milk 1L", "Dairy", 60, 100, True, (5,), 5), cat, basics)
    today = dt.date.today()
    drv.receive_stock(a, wh, sup, [{"product_id": pid, "unit_cost": 60, "quantity": 40, "batch_no": "M-001",
                                    "expiry_date": (today + dt.timedelta(days=2)).isoformat(), "manufacturing_date": (today - dt.timedelta(days=3)).isoformat()}],
                      today.isoformat())
    cust = drv.customers(a)[0]["id"]
    drv.sell(a, wh, cust, [(pid, 15)], "Cash", 1500)                     # today's sales: about 5 a day over the 3-day minimum span
    agent = agent_service.AgentRunner(drv, a, {"LossPrevention": agent_service.loss_prevention_handler(drv, a, [wh])}, log=lambda *x: None)

    def run_it():
        drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
        return next((r for r in agent.poll_once() if r["feature"] == "LossPrevention"), {})

    print("1. Without pricing rules: listed, but nothing is proposed")
    row = run_it()
    fast = drv.count_suggestions(a, "Open", "SellFast")
    check(row.get("outcome") == "done" and len(fast) == 1, "the run finishes and lists the batch: " + row.get("summary", ""))
    f = fast[0] if fast else {}
    check(f.get("daysLeft") == 2 and f.get("batchQty") == 25 or f.get("batchQty") == 25.0, f"it knows the batch: {f.get('daysLeft')} days left, {f.get('batchQty')} units on hand")
    check((f.get("unitsAtRisk") or 0) >= 10, f"about {f.get('unitsAtRisk')} units are expected to be left, worth {f.get('valueAtRiskAtCost')} at cost")
    check("pricing rules" in (f.get("reason") or ""), "it says to set the pricing rules to get a discount suggestion")
    check(not f.get("proposalStatus"), "no markdown was proposed without rules")

    print("2. With pricing rules: a discount is suggested and proposed through the Approval Center")
    drv.set_pricing_policy(a, "Approval", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=6)
    row = run_it()
    fast = drv.count_suggestions(a, "Open", "SellFast")
    f = fast[0] if fast else {}
    check((f.get("suggestedDiscountPct") or 0) > 0 and (f.get("suggestedPrice") or 0) < 100, f"suggested {f.get('suggestedDiscountPct')}% off, to {f.get('suggestedPrice')}")
    check(f.get("proposalStatus") == "Proposed", "the markdown is proposed and waiting: " + str(f.get("proposalStatus")))
    q = drv._call("GET", "/api/Pricing/Approvals", a.token)
    check(q["summary"]["waiting"] == 1, "one price proposal is waiting in the Approval Center")
    check("1 markdown(s) proposed" in row.get("summary", ""), "the run says so: " + row.get("summary", ""))

    print("3. A repeat run does not propose it again")
    row = run_it()
    q = drv._call("GET", "/api/Pricing/Approvals", a.token)
    check(q["summary"]["waiting"] == 1 and "0 markdown(s) proposed" in row.get("summary", ""), "still one proposal: " + row.get("summary", ""))

    print("4. It is a store task, and a decision sticks")
    tasks = drv.hub_tasks(a)
    sell = [t for t in tasks["items"] if t["kind"] == "SellFast"]
    check(len(sell) == 1 and sell[0]["severity"] == "Act" and tasks.get("sellFast") == 1, "My tasks lists 1 'Sell fast' item, urgent (2 days left)")
    st, _ = drv._call("POST", f"/api/ai/count-suggestions/{sell[0]['id']}/decision", a.token, json_body={"decision": "Handled"}, raw=True)
    check(st == 200, "marking it Handled works")
    run_it()
    again = drv.count_suggestions(a, "Open", "SellFast")
    check(not any(x.get("batchId") == f.get("batchId") for x in again), "a handled batch is not listed again for a few days")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

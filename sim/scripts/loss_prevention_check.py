"""Live check of AI Product Loss Prevention on a fresh throwaway shop: run-now, a delivery with no receiving report is ranked and worded,
the suggestion appears in My tasks, a person's decision sticks and is not nagged about again, and the feature switch is enforced.

    python scripts/loss_prevention_check.py
"""
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
    run = "lp-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Loss Prevention Store", "Demo", "Owner", f"{run}@lp.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    sup = drv.add_supplier(a, "LP Supplier", 1)
    p_ok = drv.add_product(a, ProductSpec("LP-1", "Reported goods", "Grocery", 40, 70, False), cat, basics)
    p_gap = drv.add_product(a, ProductSpec("LP-2", "Unreported goods", "Grocery", 80, 120, False), cat, basics)
    for pid in (p_ok, p_gap):                                              # opening stock: each product's first receipt
        drv.receive_stock(a, wh, sup, [{"product_id": pid, "unit_cost": 40 if pid == p_ok else 80, "quantity": 20}], "2026-10-01")
    pur = drv.receive_stock(a, wh, sup, [{"product_id": p_ok, "unit_cost": 40, "quantity": 30}, {"product_id": p_gap, "unit_cost": 80, "quantity": 30}], "2026-10-05")
    drv.receiving_report(a, wh, pur, p_ok, 30, 30, "all there")           # only one of the two deliveries is reported
    agent = agent_service.AgentRunner(drv, a, {"LossPrevention": agent_service.loss_prevention_handler(drv, a, [wh])}, log=lambda *x: None)

    print("1. The feature can be run now")
    ctl = {f["key"]: f for f in drv._call("GET", "/api/ai/control", a.token)}
    check(ctl["LossPrevention"]["canRun"] and ctl["LossPrevention"]["buildState"] == "Built", "AI Product Loss Prevention has a Run now")

    print("2. A run ranks the unreported delivery")
    st, _ = drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
    res = agent.poll_once()
    row = next((r for r in res if r["feature"] == "LossPrevention"), {})
    check(st == 202 and row.get("outcome") == "done", "the run finishes: " + row.get("summary", ""))
    check("1 with an unreported delivery" in row.get("summary", ""), "only the delivery without a receiving report counts as unreported (the reported one is matched to its purchase)")
    items = drv.count_suggestions(a)
    gap = next((i for i in items if i["productId"] == p_gap), None)
    check(gap is not None and "no receiving report" in gap["reason"], "the unreported delivery is on the list, with the reason in words")
    ok_item = next((i for i in items if i["productId"] == p_ok), None)
    check(gap is not None and (ok_item is None or gap["score"] > ok_item["score"]), "it ranks above the delivery that was reported")
    check(gap is not None and gap["onHand"] > 0 and gap["valueAtCost"] > 0, "it shows how much is on the shelf and what that is worth at cost")

    print("3. It is a task for the store manager")
    tasks = drv.hub_tasks(a)
    counts = [t for t in tasks["items"] if t["kind"] == "Count"]
    check(len(counts) >= 1 and tasks.get("counts") == len(counts), f"My tasks lists {len(counts)} 'Count' item(s)")

    print("4. A decision sticks and the list does not nag")
    st, _ = drv._call("POST", f"/api/ai/count-suggestions/{gap['id']}/decision", a.token, json_body={"decision": "Counted"}, raw=True)
    check(st == 200, "marking it Counted works")
    st, _ = drv._call("POST", f"/api/ai/count-suggestions/{gap['id']}/decision", a.token, json_body={"decision": "Dismissed"}, raw=True)
    check(st == 400, "it cannot be decided twice")
    drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
    row = next((r for r in agent.poll_once() if r["feature"] == "LossPrevention"), {})
    again = drv.count_suggestions(a)
    check(not any(i["productId"] == p_gap for i in again), "the product that was just counted is not suggested again: " + row.get("summary", ""))

    print("5. The switch is enforced")
    drv._call("PUT", "/api/ai/control/LossPrevention", a.token, json_body={"enabled": False})
    st, o = drv.post_count_suggestions(a, [wh], [{"WarehouseId": wh, "ProductId": p_ok, "Score": 5, "Reason": "x"}])
    check(st == 422 and o.get("code") == "AI_FEATURE_OFF", "with AI Product Loss Prevention switched off PesoWeb refuses new suggestions")
    drv._call("PUT", "/api/ai/control/LossPrevention", a.token, json_body={"enabled": True})

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Live check of the Approval Center API on a fresh throwaway shop: policy settings, routing, queue, bulk approve, auto-approve,
edit-on-approve, undo and the lane permission. Uses only the local PesoWeb.

    python scripts/approval_center_check.py
"""
import datetime as dt
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import PesoWebDriver   # noqa: E402
from simpeso.verticals import ProductSpec  # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def price(drv, acct, wh, pid):
    r = drv._call("GET", f"/api/Inventory/ProductDetail/{pid}?warehouse={wh}", acct.token)
    return float(r.get("price") or r["product"]["price"])


def main() -> int:
    run = "apc-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Approval Check Store", "Demo", "Owner", f"{run}@apc.test", "Apc!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pids = []
    for i, (cost, p) in enumerate([(60, 100), (60, 100), (60, 100), (60, 100)]):
        pids.append(drv.add_product(a, ProductSpec(f"APC-{i}", f"Test item {i}", "Grocery", cost, p, False), cat, basics))
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)
    pol = drv.pricing_policy(a)
    print("1. Policy carries the Approval Center settings")
    check(all(k in pol for k in ("listPriceAutoApprove", "autoApproveMaxPct", "storeLaneMaxPct", "ownerLaneMinPct", "proposalExpiryHours")), "settings are returned")
    check(pol["listPriceAutoApprove"] is False and pol["storeLaneMaxPct"] == 5 and pol["ownerLaneMinPct"] == 8, "defaults: auto-approve off, lanes 5% and 8%")

    print("2. Proposals are routed to lanes and wait in one inbox")
    body = lambda pid, new, conf, gain=4.0: {"WarehouseId": wh, "ProductId": pid, "NewPrice": new, "Reason": "advisor", "Source": "Ai", "PredictionRef": f"apc-{pid}",
                                              "Confidence": conf, "ExpectedGainPerDay": gain, "ExpectedGainConservativePerDay": gain * 0.7, "Evidence": "learned -1.4"}
    st1, o1 = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body=body(pids[0], 103, "learned"), raw=True)
    st2, o2 = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body=body(pids[1], 103, "assumed"), raw=True)
    st3, o3 = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body=body(pids[2], 110, "learned"), raw=True)
    print(f"   +3% learned -> lane {o1.get('lane')}; +3% assumed -> lane {o2.get('lane')}; +10% learned -> lane {o3.get('lane')}")
    check((st1, st2, st3) == (202, 202, 202), "all three wait for approval")
    check((o1["lane"], o2["lane"], o3["lane"]) == ("Store manager", "Pricing manager", "Pricing manager"), "routed by size and evidence quality")
    q = drv._call("GET", "/api/Pricing/Approvals", a.token)
    check(q["summary"]["waiting"] == 3 and len(q["items"]) == 3, "the inbox lists the 3 waiting items")
    it = next(i for i in q["items"] if i["id"] == o1["priceChangeId"])
    check(it["lowRisk"] and it["canApprove"] and len(it["checks"]) >= 4 and it["gainConservativePerDay"] == 2.8, "an item carries low-risk flag, rule checks and the conservative gain")
    only_store = drv._call("GET", "/api/Pricing/Approvals?lane=Store%20manager", a.token)
    check(len(only_store["items"]) == 1, "the lane filter works")

    print("3. Bulk approve covers only low-risk items")
    r = drv._call("POST", "/api/Pricing/ApproveBulk", a.token, json_body={"PriceChangeIds": [o1["priceChangeId"], o2["priceChangeId"]]})
    codes = {x["priceChangeId"]: x["code"] for x in r["results"]}
    check(r["approved"] == 1 and codes[o2["priceChangeId"]] == "NOT_LOW_RISK", "the low-risk one is approved, the assumed one is skipped")
    check(price(drv, a, wh, pids[0]) == 103 and price(drv, a, wh, pids[1]) == 100, "only the low-risk price changed")

    print("4. Approve at an edited price")
    st, o = drv._call("POST", "/api/Pricing/ApproveListPrice", a.token, json_body={"PriceChangeId": o3["priceChangeId"], "NewPrice": 106}, raw=True)
    check(st == 200 and o["appliedPrice"] == 106 and price(drv, a, wh, pids[2]) == 106, "approved at 106 instead of 110")

    print("5. Undo restores the previous price and is logged")
    st, o = drv._call("POST", "/api/Pricing/UndoListPrice", a.token, json_body={"PriceChangeId": o3["priceChangeId"]}, raw=True)
    check(st == 200 and price(drv, a, wh, pids[2]) == 100, "price is back to 100")
    ledger = drv.list_price_changes(a)
    check(any((r.get("reason") or "").startswith("undo of change") for r in ledger), "the undo is in the ledger")

    print("6. Auto-approve inside tight limits (off by default, switched on for this test)")
    drv._call("PUT", "/api/Pricing/Policy", a.token, json_body={"AutonomyMode": "Autonomous", "HardMarginFloorPct": 5, "SoftMarginFloorPct": 10, "MaxDiscountPct": 50,
                                                                 "MaxChangesPerSkuPerHour": 10, "ListPriceAutoApprove": True})
    st, o = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body=body(pids[3], 102, "learned"), raw=True)
    check(st == 200 and o["code"] == "AUTO_APPROVED" and price(drv, a, wh, pids[3]) == 102, "a small learned AI change is applied at once and logged as auto-approved")
    st, o = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body=body(pids[3], 108, "learned"), raw=True)
    check(st == 202, "a bigger change still waits for a person")
    q = drv._call("GET", "/api/Pricing/Approvals", a.token)
    check(q["summary"]["autoApprovedToday"] >= 1 and q["summary"]["approvedToday"] >= 1, "the counters show manual and auto approvals today")

    print("7. Bad settings are refused")
    st, o = drv._call("PUT", "/api/Pricing/Policy", a.token, json_body={"AutonomyMode": "Autonomous", "HardMarginFloorPct": 5, "SoftMarginFloorPct": 10, "MaxDiscountPct": 50,
                                                                         "MaxChangesPerSkuPerHour": 10, "StoreLaneMaxPct": 9, "OwnerLaneMinPct": 4}, raw=True)
    check(st == 400, "an owner lane threshold below the store lane size is rejected")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

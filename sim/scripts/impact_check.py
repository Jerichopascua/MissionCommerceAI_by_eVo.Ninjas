"""Live check of AI Impact on a fresh throwaway shop with two branches. Sales are dated back with SQL (test bench only) so there are
real "before" and "after" days: branch A gets an applied AI price change four days ago, branch B is the control (AI markdowns off).

    python scripts/impact_check.py
"""
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso.verticals import ProductSpec           # noqa: E402

BASE = "http://localhost:5071"
SERVER, DATABASE = r"(localdb)\MSSQLLocalDB", "PesoWeb_MissionDev"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def sql(q):
    subprocess.run(["sqlcmd", "-S", SERVER, "-d", DATABASE, "-E", "-Q", "SET NOCOUNT ON; " + q], check=True, capture_output=True, text=True)


def main() -> int:
    run = "imp-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Impact Store", "Demo", "Owner", f"{run}@imp.test", "Hub!123456")
    tid = int(a.tenant_id)
    wh_a = a.warehouse_id
    sql(f"UPDATE Users SET Subscription = 3 WHERE Id = {int(a.user_id)};")      # test bench: a plan that allows more than one branch
    wh_b = drv.add_branch(a, "Control branch", "Quezon City", 2)
    drv.grant_branch(a, wh_b)
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pid = drv.add_product(a, ProductSpec("IM-1", "Test item", "Grocery", 60, 100, False), cat, basics)
    sup = drv.add_supplier(a, "Impact Supplier", 1)
    for wh in (wh_a, wh_b):
        drv.receive_stock(a, wh, sup, [{"product_id": pid, "unit_cost": 60, "quantity": 500}], "2026-10-01")
    cust = drv.customers(a)[0]["id"]
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)
    drv._call("PUT", f"/api/ai/branch-settings/{wh_b}", a.token, json_body={"PricingEnabled": False})

    print("1. Nothing to compare yet")
    r = drv._call("GET", "/api/ai/hub/impact?days=14", a.token)
    check(r["available"] is False and "has not changed any price" in r["message"], "before the AI changes a price the page says so")

    print("2. Five days of sales before, an AI price change, five days after (dated back with SQL)")
    for wh in (wh_a, wh_b):
        for _ in range(5):
            drv.sell(a, wh, cust, [(pid, 1)], "Cash", 100)
    sql(f"UPDATE Sales SET SaleDate = DATEADD(day, -6, SaleDate) WHERE TenantID = {tid}; "
        f"UPDATE InventoryTransactions SET TransactionDate = DATEADD(day, -6, TransactionDate) WHERE TenantID = {tid} AND TransactionType = 'SALE_OUT';")
    st, body = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh_a, "ProductId": pid, "NewPrice": 106, "Source": "Ai", "Confidence": "learned"}, raw=True)
    cid = body.get("priceChangeId")
    drv._call("POST", "/api/Pricing/ApproveListPrice", a.token, json_body={"PriceChangeId": cid}, raw=True)      # a list price always waits for a person
    sql(f"UPDATE PriceChanges SET CreatedAt = DATEADD(day, -4, GETDATE()) WHERE TenantID = {tid};")
    for wh, price in ((wh_a, 106), (wh_b, 100)):
        for _ in range(5):
            drv.sell(a, wh, cust, [(pid, 1)], "Cash", price)
    sql(f"UPDATE Sales SET SaleDate = DATEADD(day, -2, SaleDate) WHERE TenantID = {tid} AND SaleDate >= CAST(GETDATE() AS date); "
        f"UPDATE InventoryTransactions SET TransactionDate = DATEADD(day, -2, TransactionDate) WHERE TenantID = {tid} AND TransactionType = 'SALE_OUT' AND TransactionDate >= CAST(GETDATE() AS date);")

    r = drv._call("GET", "/api/ai/hub/impact?days=14", a.token)
    check(r["available"] and r["windowDays"] == 4 and r["aiPriceChanges"] == 1, f"the comparison opens on the day of the AI change, {r.get('windowDays')} days each side")
    ch = r["change"]
    check(ch["marginPts"] is not None and ch["marginPts"] > 0, f"the company's margin rate rose: {ch['marginPts']} points")
    rows = {b["name"]: b for b in r["branches"]}
    check(rows[next(n for n in rows if n != "Control branch")]["role"] == "Idle" and rows["Control branch"]["role"] == "Control", "the AI branch has had a list-price change but no markdown yet (Idle); the AI-off branch is the control")

    print("3. A list price lifts every branch, so it cannot make an AI branch")
    c = r["control"]
    check(c["available"] is False and "No AI markdown was applied" in c["message"], "with only an AI list-price change there is no AI branch to compare with the control")
    check(any("same at every branch" in x for x in r["caveats"]), "the page says why: a list price is the same at every branch")
    sql(f"INSERT INTO PriceChanges (TenantID, WarehouseId, ProductId, BatchId, PriceBefore, PriceAfter, DiscountPct, Reason, Source, Status, EndsAt, CreatedAt) "
        f"VALUES ({tid}, {wh_a}, {pid}, 1, 106, 95, 10, 'test markdown', 'Ai', 'Applied', DATEADD(day, -3, GETDATE()), DATEADD(day, -3, GETDATE()));")
    r = drv._call("GET", "/api/ai/hub/impact?days=14", a.token)
    c = r["control"]
    check(c["available"] and c["ai"]["branches"] == 1 and c["control"]["branches"] == 1, "once the AI has marked a price down at one branch it counts as the AI branch and the other as control")
    check(abs(c["difference"]["marginPts"]) < 0.5, f"AI against control is about zero, because the list-price rise lifted both: {c['difference']['marginPts']} points relative")
    check(c["control"]["change"]["marginPts"] > 0, "the control branch moved too, which is exactly why the comparison is not credited to the AI")
    check("relative to the control" in c["reading"], "and the page reads the result in one sentence")

    print("4. A control the AI priced is not a clean control")
    drv._call("PUT", f"/api/ai/branch-settings/{wh_b}", a.token, json_body={"PricingEnabled": True})
    r = drv._call("GET", "/api/ai/hub/impact?days=14", a.token)
    check(r["control"]["available"] is False and "No branch is set aside" in r["control"]["message"], "with every branch on, it says how to set a control up")

    drv._call("PUT", f"/api/ai/branch-settings/{wh_b}", a.token, json_body={"PricingEnabled": False})      # leave the shop as a demo: one AI branch, one control
    print(f"\n(demo shop left in place: {run}@imp.test / Hub!123456)")
    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

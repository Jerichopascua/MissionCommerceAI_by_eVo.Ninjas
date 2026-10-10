"""Live check of "put on sale" on a fresh throwaway shop: the pricing rules refuse a bad sale, a good one is accepted, the POS lists and rings
the product up at the sale price, and ending the sale brings the normal price back.

    python scripts/product_sale_check.py
"""
import datetime as dt
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
    run = "ps-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Put On Sale Store", "Demo", "Owner", f"{run}@ps.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Snacks")
    sup = drv.add_supplier(a, "Snack Supplier", 1)
    pid = drv.add_product(a, ProductSpec("PS-1", "Choco cookies 100g", "Snacks", 60, 100, True, (5,), 5), cat, basics)
    today = dt.date.today()
    drv.receive_stock(a, wh, sup, [{"product_id": pid, "unit_cost": 60, "quantity": 100, "batch_no": "B-1",
                                    "expiry_date": (today + dt.timedelta(days=200)).isoformat(),
                                    "manufacturing_date": (today - dt.timedelta(days=5)).isoformat()}], today.isoformat())
    cust = drv.customers(a)[0]["id"]
    ends = (today + dt.timedelta(days=5)).isoformat()

    def put(pct):
        return drv._call("POST", "/api/product-sales", a.token, json_body={"productId": pid, "percentOff": pct, "endsOn": ends, "note": "Weekend sale"}, raw=True)

    def pos_price():
        st, body = drv._call("GET", f"/api/sales/searchproducts?warehouse={wh}&search=Choco&page=1", a.token, raw=True)
        rows = body if isinstance(body, list) else (body.get("products") or body.get("Products") or [])
        return next((r.get("price", r.get("salePrice")) for r in rows if r.get("id") == pid), None)

    print("1. The pricing rules decide what a sale may be")
    drv.set_pricing_policy(a, "Approval", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=6)
    st, body = put(60)
    check(st == 422 and body.get("code") == "EXCEEDS_MAX_DISCOUNT" or st == 422, f"60% off is refused: {body.get('message')}")
    st, body = put(42)
    check(st == 422 and body.get("code") == "BELOW_HARD_FLOOR", f"42% off (below cost plus 5%) is refused: {body.get('message')}")
    st, body = put(0)
    check(st == 400, "0% off is not a sale")

    print("2. A good sale is accepted and the POS charges it")
    check(pos_price() == 100, f"before the sale the POS price is {pos_price()}")
    st, body = put(30)
    check(st == 200 and abs(body.get("salePrice", 0) - 70) < 0.01, f"30% off is accepted at {body.get('salePrice')}")
    check(abs((pos_price() or 0) - 70) < 0.01, f"the POS lists it at {pos_price()}")
    sale = drv.sell(a, wh, cust, [(pid, 2)], "Cash", 140)
    detail = (sale.get("saleDetails") or sale.get("details") or [{}])[0]
    check(abs(float(detail.get("salePrice", 0)) - 70) < 0.01, f"2 units are rung up at {detail.get('salePrice')} each (total {sale.get('totalAmount')})")

    print("3. It is listed, and ending it brings the normal price back")
    st, rows = drv._call("GET", "/api/product-sales", a.token, raw=True)
    mine = [r for r in rows if r["productId"] == pid]
    check(len(mine) == 1 and mine[0]["percentOff"] == 30, "the sale is on the list of sales on now")
    st, _ = drv._call("POST", f"/api/product-sales/{mine[0]['id']}/end", a.token, json_body={}, raw=True)
    check(st == 200 and pos_price() == 100, f"after ending it the POS price is {pos_price()}")
    sale = drv.sell(a, wh, cust, [(pid, 1)], "Cash", 100)
    detail = (sale.get("saleDetails") or sale.get("details") or [{}])[0]
    check(abs(float(detail.get("salePrice", 0)) - 100) < 0.01, f"1 unit is rung up at {detail.get('salePrice')}")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

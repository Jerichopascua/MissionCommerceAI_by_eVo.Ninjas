"""Prepares the Rush Sale story in the real test company (520 Minimart): a few snack and dairy products that are close to their expiry
date, today's sales of them, and then the AI Product Loss Prevention run that finds them and proposes the rush sale.

    python scripts/rush_sale_demo_data.py            (PesoWeb on :5071; take a database backup first)

What it does, all through PesoWeb's own APIs:
  1. switches expiry tracking on for the products (SQL, the same switch as the product screen)
  2. receives one batch of each, with an expiry date a few days away
  3. sells some of each today (this is the rate of sale the AI uses)
  4. sets the company's pricing rules (never below cost, at most 50% off)
  5. runs AI Product Loss Prevention (Sell fast) for every branch
"""
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso import agent_service                   # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402

BASE = "http://localhost:5071"
# product id, units received, days to expiry, units sold today
PLAN = [
    (1367, 48, 2, 12),    # Rebisco Choco Mucho
    (1019, 36, 3, 9),     # Squid Flakes Crackers
    (1370, 30, 2, 8),     # Rebisco Whoopee
    (1375, 30, 4, 6),     # Quezo Real (cheese spread)
    (1339, 24, 3, 6),     # Relish bread crumbs
]


def sql(q):
    subprocess.run(["sqlcmd", "-S", r"(localdb)\MSSQLLocalDB", "-d", "PesoWeb_MissionDev", "-E", "-b", "-Q", q], check=True, capture_output=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    drv = PesoWebDriver(BASE, "rush-sale-demo")
    a = drv.login("superuser@520minimart.test", "Abc123##")
    branches = drv._call("GET", "/api/ai/branch-settings", a.token) or []
    whs = [b["warehouseId"] for b in branches]
    wh = a.warehouse_id or whs[0]
    ids = ",".join(str(p[0]) for p in PLAN)
    print(f"{len(whs)} branch(es); using warehouse {wh}")

    sql(f"UPDATE Products SET BatchTracking=1, MonitorExpiry=1, ExpiryAlertDays=7 WHERE TenantID=6 AND Id IN ({ids})")
    drv.set_pricing_policy(a, "Approval", hard_floor=0, soft_floor=5, max_discount=50, max_changes_per_hour=6)

    today = dt.date.today()
    sup = drv.add_supplier(a, "Rush Sale Demo Supplier", 1)
    lines = []
    for pid, qty, days, _ in PLAN:
        row = drv._call("GET", f"/api/inventory/products?searchValue={pid}&pageSize=10&page=1", a.token)
        cost = next(r["cost"] for r in row["data"] if r["id"] == pid)
        lines.append({"product_id": pid, "unit_cost": cost, "quantity": qty, "batch_no": f"RUSH-{today:%m%d}-{pid}",
                      "expiry_date": (today + dt.timedelta(days=days)).isoformat(),
                      "manufacturing_date": (today - dt.timedelta(days=20)).isoformat()})
    drv.receive_stock(a, wh, sup, lines, today.isoformat())
    print("received", len(lines), "batches with expiry dates")

    cust = drv.customers(a)[0]["id"]
    sold = [(pid, sold_qty) for pid, _, _, sold_qty in PLAN]
    for pid, q in sold:
        drv.sell(a, wh, cust, [(pid, q)], "Cash", 0)
    print("sold today:", sold)

    agent = agent_service.AgentRunner(drv, a, {"LossPrevention": agent_service.loss_prevention_handler(drv, a, whs)}, log=lambda *x: None)
    drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
    row = next((r for r in agent.poll_once() if r["feature"] == "LossPrevention"), {})
    print("AI run:", row.get("outcome"), "-", row.get("summary"))
    for f in drv.count_suggestions(a, "Open", "SellFast"):
        print(f"  {f.get('product')[:34]:34} {f.get('daysLeft')}d  batch {f.get('batchQty'):>5}  at risk {f.get('unitsAtRisk'):>5}  "
              f"cost {f.get('valueAtRiskAtCost'):>8}  -> {f.get('suggestedDiscountPct')}%  {f.get('proposalStatus') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

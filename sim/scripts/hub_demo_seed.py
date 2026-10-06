"""Stage a scenario for the Intelligence Hub demo on a simulated world: at one branch, the fastest-selling products are down to about a
day of stock, so AI Replenish has something to suggest.

    PESOWEB_ROOT_PASSWORD=... python scripts/hub_demo_seed.py --run real2 --company c1 --branch 0 --count 12

This is test-bench housekeeping, done straight in the throwaway SQL database: it sets the quantity on the shelf (ProductWarehouses) and
writes no ledger rows, so nothing shows up as a loss or as shrinkage. Do not use it on a real company's data. (A stock count was tried
first and rejected: it books the difference as shrinkage, which would make the hub's shrinkage figures absurd.)
Then run AI Replenish: AI Control, Run now, or  python -m simpeso.agent_service --run real2 --company c1 --once"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import price_run, runner               # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--company", default="c1")
    ap.add_argument("--branch", type=int, default=0, help="which of the company's branches, counting from 0")
    ap.add_argument("--count", type=int, default=12, help="how many of the fastest-selling products")
    ap.add_argument("--days-left", type=float, default=1.0, help="days of stock to leave")
    ap.add_argument("--base-url", default="http://localhost:5071")
    ap.add_argument("--server", default=r"(localdb)\MSSQLLocalDB")
    ap.add_argument("--database", default="PesoWeb_MissionDev")
    args = ap.parse_args(argv)

    state = json.loads((runner.RUNS / args.run / "world.json").read_text(encoding="utf-8"))
    model = json.loads((runner.RUNS / args.run / "model.json").read_text(encoding="utf-8"))
    comp = state["companies"][args.company]
    whs = [b["warehouse_id"] for b in comp["branches"].values() if "warehouse_id" in b]
    wh = whs[args.branch]
    drv = PesoWebDriver(args.base_url, "hub-demo-seed")
    acct = drv.login(comp["owner"]["email"], comp["owner"]["password"])

    products = {p["id"]: p for p in price_run.browse(drv, acct, wh)}
    fast = sorted(((float(r), int(k.split(":")[1])) for k, r in model["rates"].items()
                   if int(k.split(":")[0]) == wh and int(k.split(":")[1]) in products), reverse=True)[:args.count]
    if not fast:
        print("no sales rates found for that branch")
        return 1
    statements = []
    for rate, pid in fast:
        qty = max(1, math.ceil(rate * args.days_left))
        statements.append(f"UPDATE ProductWarehouses SET Quantity = {qty} WHERE TenantID = {int(acct.tenant_id)} AND WarehouseId = {int(wh)} AND ProductId = {int(pid)};")
        print(f"  {products[pid]['name'][:34]:34s} {products[pid]['stock']:6.0f} -> {qty:3d}   (sells about {rate:.1f} a day)")
    subprocess.run(["sqlcmd", "-S", args.server, "-d", args.database, "-E", "-Q", "SET NOCOUNT ON; " + " ".join(statements)], check=True, capture_output=True, text=True)
    print(f"set {len(fast)} products at warehouse {wh} to about {args.days_left:g} day of stock")
    return 0


if __name__ == "__main__":
    sys.exit(main())

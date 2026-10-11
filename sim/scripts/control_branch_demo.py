"""Gives a simulated company an AI branch and a control branch with identical expiring stock, so the Hub's "AI branches against the
control branch" comparison has real numbers.

    python scripts/control_branch_demo.py [--world real2] [--company c1] [--day 410]

What it does, through PesoWeb's own APIs (nothing is written to the database directly except the expiry-tracking switch on six products):
  1. the second branch is made the control (AI markdowns off); the first stays on
  2. the same six products get an identical batch with an expiry date two days away at both branches
  3. both branches sell the same few units (the rate of sale the AI works from)
  4. AI Product Loss Prevention runs: it proposes markdowns for the batches; PesoWeb applies them at the AI branch and refuses them
     at the control branch (AI markdowns are off there)
  5. simulated shoppers then run a business day in the whole company, so they meet the lower prices at one branch and the normal ones at the other
After this, Intelligent Hub, AI Impact, with the AI start day set to today, compares the two branches.
"""
import argparse
import datetime as dt
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso import agent_service                   # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402

BASE = "http://localhost:5071"


def sql(q):
    subprocess.run(["sqlcmd", "-S", r"(localdb)\MSSQLLocalDB", "-d", "PesoWeb_MissionDev", "-E", "-b", "-Q", q], check=True, capture_output=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="real2")
    ap.add_argument("--company", default="c1")
    ap.add_argument("--day", type=int, default=410)
    ap.add_argument("--products", type=int, default=6)
    args = ap.parse_args()

    creds = io.open(ROOT / "runs" / "CREDENTIALS.txt", encoding="utf-8", errors="replace").read()
    m = re.search(rf"{args.company} OWNER tenant (\d+): (owner\.{args.company}\.s21\.{args.world}@simworld\.test) / (\S+)", creds)
    tenant, email, password = int(m.group(1)), m.group(2), m.group(3)
    drv = PesoWebDriver(BASE, "control-demo")
    a = drv.login(email, password)

    branches = drv._call("GET", "/api/ai/branch-settings", a.token)
    ai_wh, ctl_wh = branches[0]["warehouseId"], branches[1]["warehouseId"]
    print(f"AI branch {branches[0]['name']} ({ai_wh}); control branch {branches[1]['name']} ({ctl_wh})")
    for b, on in ((branches[0], True), (branches[1], False)):
        drv._call("PUT", f"/api/ai/branch-settings/{b['warehouseId']}", a.token, raw=True,
                  json_body={"pricingEnabled": on, "clearanceStartHour": None, "region": b.get("region"),
                             "salesTargetPerDay": b.get("salesTargetPerDay"), "wasteTargetPct": b.get("wasteTargetPct")})

    # six products with room in the margin, so a markdown is allowed
    rows = []
    for page in (1, 2, 3):
        got = drv._call("GET", f"/api/inventory/products?pageSize=250&page={page}", a.token)
        rows += got.get("data", [])
    pool = [r for r in rows if not r.get("hasVariants") and r.get("cost", 0) > 0 and r.get("price", 0) >= max(10, r["cost"] * 1.6)]
    pool.sort(key=lambda r: -r["price"])
    picks = pool[:args.products]
    if len(picks) < args.products:
        print("not enough products with a margin to mark down:", len(picks))
        return 1
    ids = ",".join(str(p["id"]) for p in picks)
    sql(f"UPDATE Products SET BatchTracking=1, MonitorExpiry=1, ExpiryAlertDays=7 WHERE TenantID={tenant} AND Id IN ({ids})")
    print("products:", ", ".join(p["productName"][:24] for p in picks))

    today = dt.date.today()
    sup = drv.add_supplier(a, "Control Demo Supplier", 1)
    cust = drv.customers(a)[0]["id"]
    for wh in (ai_wh, ctl_wh):
        lines = [{"product_id": p["id"], "unit_cost": p["cost"], "quantity": 40, "batch_no": f"CTL-{today:%m%d}-{p['id']}-{wh}",
                  "expiry_date": (today + dt.timedelta(days=2)).isoformat(), "manufacturing_date": (today - dt.timedelta(days=10)).isoformat()}
                 for p in picks]
        drv.receive_stock(a, wh, sup, lines, today.isoformat())
        for p in picks:                                         # the same rate of sale at both branches
            drv.sell(a, wh, cust, [(p["id"], 6)], "Cash", 0)
    print("identical batches received and the same units sold at both branches")

    agent = agent_service.AgentRunner(drv, a, {"LossPrevention": agent_service.loss_prevention_handler(drv, a, [ai_wh, ctl_wh])},
                                      log=lambda *x: None)
    drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
    row = next((r for r in agent.poll_once() if r["feature"] == "LossPrevention"), {})
    print("AI run:", row.get("outcome"), "-", row.get("summary"))
    for f in drv.count_suggestions(a, "Open", "SellFast"):
        if f["product"] in {p["productName"] for p in picks}:
            print(f"   {f['branch'][:30]:30} {f['product'][:26]:26} {f.get('suggestedDiscountPct')}%  {f.get('proposalStatus') or '-'}")

    print("simulated shoppers, one business day ...")
    r = subprocess.run([sys.executable, "-m", "simpeso.runner", "day", "--run", args.world, "--day", str(args.day), "--datasets", "simulated-rules"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    print((r.stdout or r.stderr).strip().splitlines()[-4:])
    imp = drv._call("GET", f"/api/ai/hub/impact?days=14&switchDate={today.isoformat()}", a.token)
    ctl = imp.get("control") or {}
    print("control comparison available:", ctl.get("available"))
    if ctl.get("available"):
        print(" ", ctl.get("reading"))
        print("  difference:", ctl.get("difference"))
    else:
        print(" ", ctl.get("message"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

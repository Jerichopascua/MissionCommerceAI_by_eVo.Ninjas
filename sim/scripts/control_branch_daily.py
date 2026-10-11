"""One more day of the AI-branch-against-control experiment on a simulated company (run it once a day, on a new day each time).

    python scripts/control_branch_daily.py --day 412 [--start-day 2026-10-14]

It runs one simulated business day (the shoppers buy at both branches), lets AI Product Loss Prevention act (it marks down batches at the AI
branch and PesoWeb refuses it at the control branch), and prints what the Hub's AI Impact says for the start day you choose.

Why daily: PesoWeb stamps every sale with the real clock and AI Impact needs 3 full days before and 3 after the start day, so the comparison
cannot be fast-forwarded. Set the control up once with scripts/control_branch_demo.py. Then run this each day. With the start day on D, the
comparison is available on D + 3 (the three days before D, and D, D+1, D+2, must each have had a run).
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


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="real2")
    ap.add_argument("--company", default="c1")
    ap.add_argument("--day", type=int, required=True, help="a number not used before for this world (it only picks the dice)")
    ap.add_argument("--start-day", default=None, help="the AI start day to compare from, YYYY-MM-DD")
    args = ap.parse_args()

    creds = io.open(ROOT / "runs" / "CREDENTIALS.txt", encoding="utf-8", errors="replace").read()
    m = re.search(rf"{args.company} OWNER tenant (\d+): (owner\.{args.company}\.s21\.{args.world}@simworld\.test) / (\S+)", creds)
    drv = PesoWebDriver("http://localhost:5071", "control-daily")
    a = drv.login(m.group(2), m.group(3))
    whs = [b["warehouseId"] for b in drv._call("GET", "/api/ai/branch-settings", a.token)]

    r = subprocess.run([sys.executable, "-m", "simpeso.runner", "day", "--run", args.world, "--day", str(args.day), "--datasets", "simulated-rules"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    print("business day:", " ".join((r.stdout or r.stderr).split())[-160:])

    agent = agent_service.AgentRunner(drv, a, {"LossPrevention": agent_service.loss_prevention_handler(drv, a, whs)}, log=lambda *x: None)
    drv._call("POST", "/api/ai/control/run/LossPrevention", a.token, raw=True)
    row = next((x for x in agent.poll_once() if x["feature"] == "LossPrevention"), {})
    print("AI run:", row.get("summary"))

    q = f"?days=14&switchDate={args.start_day}" if args.start_day else "?days=14"
    imp = drv._call("GET", "/api/ai/hub/impact" + q, a.token)
    ctl = imp.get("control") or {}
    print("start day:", str(imp.get("switchDate"))[:10], "| days compared:", imp.get("windowDays"), "| available:", imp.get("available"))
    if ctl.get("available"):
        print("AI branches against control:", ctl.get("reading"))
        print("difference:", ctl.get("difference"))
    else:
        print((ctl.get("message") or imp.get("message") or "")[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())

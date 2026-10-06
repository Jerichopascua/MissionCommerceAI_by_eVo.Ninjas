"""AI Customer Mission on a simulated world: classify the baskets, score the classifier against what shoppers were really doing, and post
each branch's mission picture to PesoWeb.

    PESOWEB_ROOT_PASSWORD=... python scripts/mission_run.py --run real2 --company c1 --days 14 [--post]

The classifier sees only hour, lines, units, value and perishable-or-not for each basket. The shoppers' hidden mission is used only to
score it. `--post` sends the result to the company's Intelligence Hub (Customer missions)."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import ai_hook, mission_sim, runner     # noqa: E402
from simpeso.driver import PesoWebDriver             # noqa: E402


def load(run, base_url):
    import argparse as ap
    ns = ap.Namespace(run=run, base_url=base_url, seed=21, profile="smoke", policy="off", calibration=None, calib_weight=0.5)
    return runner._load(ns)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--company", default="c1")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--first-day", type=int, default=300, help="the first virtual day to replay (any day the world has not used)")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--base-url", default="http://localhost:5071")
    args = ap.parse_args(argv)

    ctx = load(args.run, args.base_url)
    sim = mission_sim.sim_baskets(ctx, list(range(args.first_day, args.first_day + args.days)))
    mine = {k: v for k, v in sim.items() if k[0] == args.company}
    result = mission_sim.score_sim(mine)
    print(f"{result['baskets']} baskets at {len(mine)} branches of {args.company}; the classifier agrees with the shoppers' real mission on {result['agreement']:.0%}")
    for truth, s in result["by_truth"].items():
        print(f"   real mission {truth:18s} {s['baskets']:5d} baskets, agreement {s['agreement']:.0%}")
    if not args.post:
        return 0
    drv = ctx.driver
    owner = ctx.owner(args.company)
    comp = ctx.state["companies"][args.company]
    items, whs = [], []
    for (ck, bk), rows in sorted(mine.items()):
        wh = comp["branches"][bk]["warehouse_id"]
        whs.append(wh)
        items += mission_sim.rows_for(wh, [b for _, b in rows], args.days)
    status, body = drv.post_missions(owner, whs, items)
    print("posted:", status, body)
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())

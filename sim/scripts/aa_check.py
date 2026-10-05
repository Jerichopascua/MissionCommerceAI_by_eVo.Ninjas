"""A/A check: are two "twin" worlds really twins? Run the same trial day in both with NO AI and NO price changes and compare.

    PESOWEB_ROOT_PASSWORD=... python scripts/aa_check.py --run-a real2 --run-b real3 --days 214-216
If the worlds are twins the differences are small and have no sign pattern; a steady gap means the worlds started from different
states (customer memory, history) and every AI-versus-no-AI comparison between them is biased by that gap. Prices must be at the
catalog prices in both (the script checks and stops if not)."""
import argparse
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from showcase import load_ctx, price_snapshot                      # noqa: E402
from showcase_days import parse_days                                # noqa: E402
from simpeso import ai_hook, equalize, proof                        # noqa: E402

KEYS = ("revenue", "margin", "waste_pesos", "net", "units")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", default="real2")
    ap.add_argument("--run-b", default="real3")
    ap.add_argument("--days", default="214-216")
    ap.add_argument("--no-equalize", action="store_true", help="skip the stock top-up and shared lot rates (shows the raw gap)")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    args = ap.parse_args(argv)
    ctxs = [load_ctx(r, args.base_url) for r in (args.run_a, args.run_b)]
    hooks = [ai_hook.AiHooks(c, agent_on=False) for c in ctxs]
    for h in hooks:
        h.load_model()
    for c, h, name in zip(ctxs, hooks, (args.run_a, args.run_b)):
        ref = {(i["company"], i["code"]): i["list_price"] for i in h._catalog.values()}
        moved = sum(1 for k, a in price_snapshot(c, h).items() if abs(a["price"] - ref[k]) > 0.005)
        if moved:
            print(f"{name}: {moved} prices differ from the catalog; restore the database first")
            return 2
    rows = []
    if not args.no_equalize:
        print(f"rates aligned for {equalize.align_rates(hooks[1], hooks[0])} products; the second world's rates are used in both")
    for day in parse_days(args.days):
        if not args.no_equalize:
            print(f"day {day}: cleared {[equalize.clear_leftover_lots(c, h) for c, h in zip(ctxs, hooks)]} old lot batches, topped up {[equalize.top_up_stock(c, h, tag=f'top{day}') for c, h in zip(ctxs, hooks)]} lines")
        m = [proof.metrics_from(h.run_trial(day)) for h in hooks]
        rows.append({k: m[0][k] - m[1][k] for k in KEYS})
        print(f"day {day}: {args.run_a} minus {args.run_b}: " + ", ".join(f"{k} {rows[-1][k]:+,.0f}" for k in KEYS) + f"   (b: revenue {m[1]['revenue']:,.0f}, units {m[1]['units']:.0f})")
    print("mean difference: " + ", ".join(f"{k} {statistics.mean(r[k] for r in rows):+,.0f}" for k in KEYS))
    return 0


if __name__ == "__main__":
    sys.exit(main())

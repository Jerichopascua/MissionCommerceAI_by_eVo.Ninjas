"""Several more trial days after the showcase flow, to separate the two things the AI did and to average out day-to-day noise.

    PESOWEB_ROOT_PASSWORD=... python scripts/showcase_days.py --days-on 204-208 --days-off 209-213

Run after scripts/showcase.py (the AI world already holds the approved list prices). For every day the no-AI world (base) runs the
same shoppers and the same short-dated lots at the original prices. The AI world runs with the markdown agent ON for the first
set of days and OFF for the second set, always at the new list prices. So, day by day against the same base day:
  * AI world, agent OFF minus base = the effect of the new list prices alone;
  * AI world, agent ON minus AI world, agent OFF (compared as differences to base) = what the markdown agent adds on top.
Writes sim/runs/showcase_days.json and showcase_days.md."""
import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from showcase import load_ctx, price_snapshot                      # noqa: E402
from simpeso import ai_hook, equalize, proof, runner                # noqa: E402

KEYS = ("revenue", "margin", "waste_pesos", "net", "units")


def parse_days(text: str) -> list:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def mean_diff(rows, key):
    return statistics.mean(r[key] for r in rows)


def summarize(base_rows: list, on_rows: list, off_rows: list) -> dict:
    """Each list holds metrics dicts in day order; on_rows and off_rows are paired with the base rows of their own days."""
    def paired(ai_rows, base):
        return [{k: a[k] - b[k] for k in KEYS} for a, b in zip(ai_rows, base)]
    n_on = len(on_rows)
    d_on, d_off = paired(on_rows, base_rows[:n_on]), paired(off_rows, base_rows[n_on:n_on + len(off_rows)])
    out = {"days_on": n_on, "days_off": len(off_rows), "vs_base_agent_on": {}, "vs_base_agent_off": {}}
    for label, rows in (("vs_base_agent_on", d_on), ("vs_base_agent_off", d_off)):
        for k in KEYS:
            vals = [r[k] for r in rows]
            better = (lambda v: v < 0) if k == "waste_pesos" else (lambda v: v > 0)
            out[label][k] = {"mean": statistics.mean(vals), "min": min(vals), "max": max(vals), "days_better": sum(1 for v in vals if better(v)), "of": len(vals)}
    out["agent_adds"] = {k: out["vs_base_agent_on"][k]["mean"] - out["vs_base_agent_off"][k]["mean"] for k in KEYS}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-run", default="real2")
    ap.add_argument("--base-run", default="real3")
    ap.add_argument("--days-on", default="204-208")
    ap.add_argument("--days-off", default="209-213")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    args = ap.parse_args(argv)
    days_on, days_off = parse_days(args.days_on), parse_days(args.days_off)

    ctx_ai, ctx_base = load_ctx(args.ai_run, args.base_url), load_ctx(args.base_run, args.base_url)
    hooks_ai, hooks_base = ai_hook.AiHooks(ctx_ai, agent_on=True), ai_hook.AiHooks(ctx_base, agent_on=False)
    hooks_ai.load_model()
    hooks_base.load_model()
    # shoppers react to the price they see now relative to the catalog price the world was built with
    ref = {(i["company"], i["code"]): i["list_price"] for i in hooks_ai._catalog.values()}
    now = price_snapshot(ctx_ai, hooks_ai)
    for key, a in now.items():
        r = a["price"] / ref[key]
        if abs(r - 1.0) > 1e-9:
            hooks_ai.price_over[key] = r
    changed = len(hooks_ai.price_over)
    print(f"AI world holds {changed} changed list prices; base world is at the original prices")

    base_rows, on_rows, off_rows, log = [], [], [], []
    equalize.align_rates(hooks_base, hooks_ai)
    for day in days_on + days_off:
        agent_on = day in days_on
        for c, h in ((ctx_ai, hooks_ai), (ctx_base, hooks_base)):
            equalize.clear_leftover_lots(c, h)
            equalize.top_up_stock(c, h, tag=f"top{day}")
        hooks_base.agent_on = False
        mb = proof.metrics_from(hooks_base.run_trial(day))
        hooks_ai.agent_on = agent_on
        ma = proof.metrics_from(hooks_ai.run_trial(day))
        base_rows.append(mb)
        (on_rows if agent_on else off_rows).append(ma)
        log.append({"day": day, "agent_on": agent_on, "base": mb, "ai": ma})
        print(f"day {day} agent {'ON ' if agent_on else 'OFF'}: net base {mb['net']:8.0f} ai {ma['net']:8.0f} | waste base {mb['waste_pesos']:7.0f} ai {ma['waste_pesos']:7.0f} | margin base {mb['margin']:7.0f} ai {ma['margin']:7.0f}")
    s = summarize(base_rows, on_rows, off_rows)
    (runner.RUNS / "showcase_days.json").write_text(json.dumps({"days": log, "summary": s}, indent=1), encoding="utf-8")

    def row(label, d):
        return (f"| {label} | {d['revenue']['mean']:+,.0f} | {d['margin']['mean']:+,.0f} | {d['waste_pesos']['mean']:+,.0f} | {d['net']['mean']:+,.0f} "
                f"({d['net']['days_better']} of {d['net']['of']} days better) |")
    L = [f"# Showcase over more days: {args.ai_run} (AI world) against {args.base_run} (no AI)", "",
         f"AI world holds {changed} approved list-price changes. Mean difference to the no-AI world on the same day (pesos per trial day; waste: negative is better).", "",
         "| AI world setting | Revenue | Gross margin | Waste | Net (margin minus waste) |", "|---|---|---|---|---|",
         row(f"New prices, markdown agent ON ({s['days_on']} days)", s["vs_base_agent_on"]),
         row(f"New prices, markdown agent OFF ({s['days_off']} days)", s["vs_base_agent_off"]), "",
         f"What the markdown agent adds on top of the new prices (difference of the two rows): revenue {s['agent_adds']['revenue']:+,.0f}, margin {s['agent_adds']['margin']:+,.0f}, "
         f"waste {s['agent_adds']['waste_pesos']:+,.0f}, net {s['agent_adds']['net']:+,.0f}.", "",
         "Caveats: the two settings run on different days, so their difference is an estimate, not a controlled comparison. Shoppers' price response is the simulator's own hidden assumption. "
         "Each trial day is independent short-dated stock, not a month of trading. Same shoppers and lots in both worlds on a given day.", ""]
    (runner.RUNS / "showcase_days.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())

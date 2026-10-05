"""Browse every product of one company through PesoWeb's own API (name, COST, price, stock) and suggest selling prices that
maximise profit, plus the margin price for each product (the floor the markdown agent can use later).

    PESOWEB_ROOT_PASSWORD=... python scripts/price_advice.py --run real2 --company c1

Needs a world that has had its history phase (`python -m simpeso.ai_hook history --run real2`), because the sales rate and the
learned price sensitivity come from there. Writes sim/runs/price-advice-<run>-<company>.json and .md (git-ignored: real
products and prices). Suggestions only: nothing is changed in PesoWeb."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / "ai")]

from missionai import price_advisor as pa    # noqa: E402
from simpeso import runner                   # noqa: E402
from simpeso.driver import PesoWebDriver     # noqa: E402

from simpeso.price_run import browse, suggestions_for, PRIOR_BETA   # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--company", default="c1")
    ap.add_argument("--base-url", default="http://localhost:5071")
    ap.add_argument("--step", type=int, default=pa.DEFAULT_STEP_PCT, help="largest price move per review, percent")
    args = ap.parse_args(argv)
    run_dir = runner.RUNS / args.run
    state = json.loads((run_dir / "world.json").read_text(encoding="utf-8"))
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    comp = state["companies"][args.company]
    drv = PesoWebDriver(args.base_url, "price-advice")
    acct = drv.login(comp["owner"]["email"], comp["owner"]["password"])
    whs = [b["warehouse_id"] for b in comp["branches"].values() if "warehouse_id" in b]
    products, sugg, policy = suggestions_for(drv, acct, whs, model, args.step)
    summary = pa.summarize(sugg)
    by_id = {p["id"]: p for p in products}
    acts = sorted([s for s in sugg if s.status in ("raise", "lower")], key=lambda s: -s.profit_gain_per_day)
    alerts = [s for s in sugg if s.status == "margin_alert"]
    perish = [s for s in sugg if by_id[s.product_id]["perishable"]]
    out = {"run": args.run, "company": args.company, "policy": {k: policy[k] for k in ("autonomyMode", "hardMarginFloorPct", "softMarginFloorPct", "maxDiscountPct")},
           "step_pct": args.step, "summary": summary, "suggestions": [s.to_dict() for s in sugg]}
    (runner.RUNS / f"price-advice-{args.run}-{args.company}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    L = [f"# Price advice for {args.company} ({args.run}): browsed {len(products)} products with their cost", "",
         f"Policy: hard floor {policy['hardMarginFloorPct']}%, soft floor {policy['softMarginFloorPct']}%, max markdown {policy['maxDiscountPct']}%. Largest move per review: {args.step}%.",
         "Suggestions only. Nothing was changed in PesoWeb. THESE ARE HYPOTHESES TO TEST: most rest on an assumed price sensitivity, and there is no competitor price feed, so thin-margin staples that are priced to match a rival "
         "need an owner check, and ideally a price test on a few branches, before any raise.", "",
         f"**Summary:** {json.dumps(summary['by_status'])}. Conservative expected gain (if customers are one step more price-sensitive than assumed): about {summary['conservative_gain_per_day']:.0f} pesos a day; "
         f"under the assumed sensitivity about {summary['expected_profit_gain_per_day']:.0f}, against a profit of about {summary['profit_per_day_now_on_products_with_evidence']:.0f} a day today on the products with sales evidence. "
         f"{summary['suggestions_on_learned_sensitivity']} suggestions use a sensitivity learned from this shop's sales, {summary['suggestions_on_assumed_sensitivity']} use an assumed one. {summary['products_below_margin_price']} products are priced below the margin price; "
         f"{summary['products_with_no_markdown_room']} sit inside the soft margin band and cannot be marked down without approval.", "",
         "## Suggested price changes (largest expected gain first)", "", "| Product | Cost | Price now | Suggested | Change | Profit/day now | Profit/day new | If customers more sensitive | Sensitivity |", "|---|---|---|---|---|---|---|---|---|"]
    for s in acts[:25]:
        L.append(f"| {s.name[:40]} | {s.cost:g} | {s.price:g} | **{s.suggested_price:g}** | {s.change_pct:+.0f}% | {s.profit_per_day_now:.1f} | {s.profit_per_day_new:.1f} | {s.profit_gain_if_more_sensitive:+.1f} | {s.beta:.2f} ({s.beta_source}) |")
    L += ["", f"## Priced below the margin price ({len(alerts)}): fix first", "", "| Product | Cost | Price now | Margin price |", "|---|---|---|---|"]
    L += [f"| {s.name[:40]} | {s.cost:g} | {s.price:g} | {s.floor_price:g} |" for s in alerts[:30]]
    L += ["", "## The margin price for the perishable products (the floor for clearance markdowns)", "",
          "| Product | Cost | Price | Margin price | Soft price | Room to lower | Status |", "|---|---|---|---|---|---|---|"]
    L += [f"| {s.name[:40]} | {s.cost:g} | {s.price:g} | {s.floor_price:g} | {s.soft_price:g} | {s.headroom_pct:.0f}% | {s.status} |" for s in sorted(perish, key=lambda s: -s.headroom_pct)]
    (runner.RUNS / f"price-advice-{args.run}-{args.company}.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print("top suggestions:")
    for s in acts[:8]:
        print(f"  {s.name[:34]:34s} cost {s.cost:>6g} price {s.price:>6g} -> {s.suggested_price:>6g} ({s.change_pct:+.0f}%)  profit/day {s.profit_per_day_now:5.1f} -> {s.profit_per_day_new:5.1f}  [{s.beta_source}]")
    print("margin price, perishables:")
    for s in sorted(perish, key=lambda s: -s.headroom_pct)[:6]:
        print(f"  {s.name[:34]:34s} cost {s.cost:>6g} price {s.price:>6g} margin price {s.floor_price:>6g} room {s.headroom_pct:4.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

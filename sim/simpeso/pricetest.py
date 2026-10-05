"""A controlled price test that turns an ASSUMED price sensitivity into a MEASURED one.

    python -m simpeso.pricetest --run real2 --treat c1,c2 --control c3,c4,c5 --products 24 --base-days 4 --test-days 6 --pct 10

Treatment companies raise the price of the chosen products through PesoWeb's own product update; control companies do not.
(A list price belongs to the whole company in PesoWeb, so the comparison is between companies that carry the same catalog.)
After the test the prices are put back. The AI side estimates the sensitivity by difference in differences (ai/missionai/
price_test.py) and the model learns from it. The simulator also measures the TRUE effective response with a paired
counterfactual on its own hidden shoppers, which the AI never sees, so we can check whether the test recovered it.
Writes sim/runs/pricetest-<run>.json (git-ignored: real products)."""
import argparse
import json
import math
import os
import sys
from pathlib import Path

from . import behavior, runner
from .ai_hook import AiHooks
from missionai import price_test                              # noqa: E402  (ai/ is on sys.path via ai_hook)

BASE_DAY0, TEST_DAY0 = 300, 320
CATEGORY = "Grocery"


def tick(price: float) -> float:
    return 0.5 if price < 50 else 1.0


def raised(price: float, pct: float) -> float:
    t = tick(price)
    new = round(price * (1 + pct / 100.0) / t) * t
    return new if new != price else price + t


def company_of_wh(state):
    return {b["warehouse_id"]: ck for ck, c in state["companies"].items() for b in c["branches"].values() if "warehouse_id" in b}


def phase_units(hooks, ctx, days, wh_company, pid_code):
    """Run trading days and return units per (company, product code), plus the days run."""
    hooks.harvest(True)                                        # move the ledger cursor past anything earlier
    for d in days:
        runner.run_day(ctx, d, log=lambda *_: None, hooks=hooks, incidents=False)
    raw = hooks.harvest(True)
    out = {}
    for (wh, pid), u in raw.items():
        ck = wh_company.get(wh)
        code = pid_code.get((ck, pid))
        if ck and code:
            out[(ck, code)] = out.get((ck, code), 0.0) + u
    return out


def true_response(ctx, codes, ratios, treat, days=30):
    """The simulator's own effective price response on its hidden shoppers: units with the raised prices over units without,
    paired on the same random numbers, for the treated companies' branches and the chosen products."""
    plan = ctx.plan
    people = behavior.make_individuals(plan, ctx.state["seed"])
    keep = {b.key for c in plan.companies if c.key in treat for b in c.branches}
    ratio = lambda branch, code: ratios.get(code, 1.0) if branch.split("-")[0] in treat else 1.0

    def units(fn):
        total = 0.0
        for d in range(1, days + 1):
            for v in behavior.day_visits(plan, people, d, ctx.state["seed"], price_ratio=fn, calib=ctx.calib):
                if v.branch in keep:
                    total += sum(q for code, q in v.lines if code in codes)
        return total
    base, treated = units(lambda b, c: 1.0), units(ratio)
    mean_x = sum(math.log(r) for r in ratios.values()) / len(ratios)
    return {"units_base": base, "units_raised": treated, "beta_true": math.log(treated / base) / mean_x}


def set_prices(ctx, hooks, companies, chosen, specs, new_price, raised: bool, ratios):
    for ck in companies:
        owner, cs = ctx.owner(ck), ctx.state["companies"][ck]
        for c in chosen:
            ctx.driver.set_product_price(owner, cs["products"][c], specs[c], cs["categories"][specs[c].category], cs["basics"],
                                         new_price[c] if raised else specs[c].price)
            if raised:
                hooks.price_over[(ck, c)] = ratios[c]
            else:
                hooks.price_over.pop((ck, c), None)


def switchback(args, ctx, hooks, chosen, specs, ratios, new_price, wh_company, pid_code) -> int:
    companies = list(ctx.state["companies"])
    plan = price_test.randomized_days(args.days, args.seed)
    print(f"switchback: {len(chosen)} products, all {len(companies)} companies, {args.days} days, raised on {sum(plan)}: {''.join('R' if r else 'n' for r in plan)}")
    raised_units, normal_units, state_raised = {}, {}, False
    for i, raised in enumerate(plan):
        if raised != state_raised:
            set_prices(ctx, hooks, companies, chosen, specs, new_price, raised, ratios)
            state_raised = raised
        u = phase_units(hooks, ctx, [TEST_DAY0 + i], wh_company, pid_code)
        target = raised_units if raised else normal_units
        for (ck, code), v in u.items():
            target[code] = target.get(code, 0.0) + v
    set_prices(ctx, hooks, companies, chosen, specs, new_price, False, ratios)          # test over: every price back
    rows = [{"product_id": c, "x": math.log(ratios[c]), "raised_units": raised_units.get(c, 0.0), "normal_units": normal_units.get(c, 0.0)} for c in chosen]
    est = price_test.switchback_estimate(rows, sum(plan), len(plan) - sum(plan))
    truth = true_response(ctx, set(chosen), ratios, set(companies))
    before = hooks.model.beta(CATEGORY)
    if est["beta"] is not None:
        hooks.model.add_estimate(CATEGORY, est["beta"], est["se"])
    after = hooks.model.beta(CATEGORY)
    cats = sorted({i["category"] for i in hooks._catalog.values()})
    hooks.save_model({c: round(hooks.model.beta(c), 2) for c in cats})
    covered = est["beta"] is not None and est["ci95"][0] <= truth["beta_true"] <= est["ci95"][1]
    result = {"run": args.run, "design": "switchback", "companies": companies, "days": args.days, "raised_days": sum(plan), "products_tested": len(chosen),
              "price_change_pct": args.pct, "estimate": {k: est[k] for k in ("beta", "se", "ci95", "reliable", "raised_units", "normal_units")},
              "truth_effective_beta": round(truth["beta_true"], 3), "interval_covers_truth": bool(covered), "assumed_beta_before": before,
              "model_beta_after": round(after, 3)}
    (runner.RUNS / f"pricetest-{args.run}.json").write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    print(json.dumps(result, indent=1, default=float))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.pricetest")
    ap.add_argument("--run", required=True)
    ap.add_argument("--treat", default="c1,c2")
    ap.add_argument("--control", default="c3,c4,c5")
    ap.add_argument("--products", type=int, default=24)
    ap.add_argument("--base-days", type=int, default=4)
    ap.add_argument("--test-days", type=int, default=6)
    ap.add_argument("--pct", type=float, default=10.0)
    ap.add_argument("--design", choices=["groups", "switchback"], default="switchback",
                    help="groups: some companies raise, others are control. switchback: every company alternates raised and normal days (default, more power)")
    ap.add_argument("--days", type=int, default=16, help="switchback: number of trading days (in balanced pairs)")
    ap.add_argument("--seed", type=int, default=7, help="switchback: seed for the random order inside each pair of days")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--calibration", default=None)
    ap.add_argument("--calib-weight", type=float, default=0.5)
    args = ap.parse_args(argv)
    treat, control = args.treat.split(","), args.control.split(",")
    ns = argparse.Namespace(run=args.run, base_url=args.base_url, seed=21, profile="smoke", policy="off", calibration=args.calibration, calib_weight=args.calib_weight)
    ctx = runner._load(ns)
    hooks = AiHooks(ctx, agent_on=False)
    hooks.load_model()
    state = ctx.state
    wh_company = company_of_wh(state)
    pid_code = {(ck, pid): code for ck, c in state["companies"].items() for code, pid in c["products"].items()}

    # the products to test: the best sellers (pooled baseline rate) among non-perishable products
    pooled = {}
    for (wh, pid), rate in hooks.rates.items():
        ck = wh_company.get(wh)
        code = pid_code.get((ck, pid))
        if code:
            pooled[code] = pooled.get(code, 0.0) + rate
    specs = {p.code: p for p in ctx.cmap[treat[0]].catalog}
    chosen = [c for c, _ in sorted(pooled.items(), key=lambda kv: -kv[1]) if c in specs and not specs[c].expiry][:args.products]
    ratios = {}
    new_price = {}
    for c in chosen:
        new_price[c] = raised(specs[c].price, args.pct)
        ratios[c] = new_price[c] / specs[c].price

    if args.design == "switchback":
        return switchback(args, ctx, hooks, chosen, specs, ratios, new_price, wh_company, pid_code)
    print(f"test: {len(chosen)} products, treatment {treat}, control {control}, price change about {args.pct:g}%")
    base = phase_units(hooks, ctx, range(BASE_DAY0, BASE_DAY0 + args.base_days), wh_company, pid_code)
    for ck in treat:                                           # the owners raise the prices
        owner = ctx.owner(ck)
        cs = state["companies"][ck]
        for c in chosen:
            ctx.driver.set_product_price(owner, cs["products"][c], specs[c], cs["categories"][specs[c].category], cs["basics"], new_price[c])
            hooks.price_over[(ck, c)] = ratios[c]
    test = phase_units(hooks, ctx, range(TEST_DAY0, TEST_DAY0 + args.test_days), wh_company, pid_code)
    for ck in treat:                                           # test over: put every price back
        owner = ctx.owner(ck)
        cs = state["companies"][ck]
        for c in chosen:
            ctx.driver.set_product_price(owner, cs["products"][c], specs[c], cs["categories"][specs[c].category], cs["basics"], specs[c].price)
        hooks.price_over = {k: v for k, v in hooks.price_over.items() if k[0] not in treat}

    def total(d, group, code):
        return sum(d.get((ck, code), 0.0) for ck in group)
    rows = [{"product_id": c, "x": math.log(ratios[c]), "treat_base": total(base, treat, c), "treat_test": total(test, treat, c),
             "control_base": total(base, control, c), "control_test": total(test, control, c)} for c in chosen]
    est = price_test.did_estimate(rows, args.base_days, args.test_days)
    truth = true_response(ctx, set(chosen), ratios, set(treat))
    before = hooks.model.beta(CATEGORY)
    if est["beta"] is not None:                                # the model learns from the test, weighted by how precise it is
        hooks.model.add_estimate(CATEGORY, est["beta"], est["se"])
    after = hooks.model.beta(CATEGORY)
    cats = sorted({i["category"] for i in hooks._catalog.values()})
    hooks.save_model({c: round(hooks.model.beta(c), 2) for c in cats})
    covered = est["beta"] is not None and est["ci95"][0] <= truth["beta_true"] <= est["ci95"][1]
    result = {"run": args.run, "treatment": treat, "control": control, "products_tested": len(chosen), "price_change_pct": args.pct,
              "base_days": args.base_days, "test_days": args.test_days, "estimate": {k: est[k] for k in ("beta", "se", "ci95", "reliable", "treated_units_test", "control_units_test")},
              "truth_effective_beta": round(truth["beta_true"], 3), "interval_covers_truth": bool(covered), "assumed_beta_before": before,
              "model_beta_after": round(after, 3),
              "units_needed_for_se_0_5_roughly": int((est["se"] / 0.5) ** 2 * (est["treated_units_test"] + est["control_units_test"])) if est["se"] else None}
    (runner.RUNS / f"pricetest-{args.run}.json").write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    print(json.dumps(result, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""PesoProfit showcase on the real catalog: the same shop twice, once with the AI and once without, one trial day each.

    PESOWEB_ROOT_PASSWORD=... python scripts/showcase.py --ai-run real2 --base-run real3 --day 201

The AI world gets the whole flow through PesoWeb's own screens' APIs:
  1. AI Pricing run (requested through AI Control, picked up by the agent runner): margin fixes for products priced below the
     margin price, then the best list-price changes -> they wait in the Approval Center;
  2. the simulated approver decides them (approve, approve half the step, or reject);
  3. shoppers then see the new prices (their price response is the simulator's hidden assumption);
  4. the trial day: short-dated lots arrive and the markdown agent works the day.
The base world sees the same shoppers and the same lots at the original real prices, with no AI.
Writes sim/runs/showcase.json and showcase.md (git-ignored: real products and prices).
Not modelled: how long an approver takes (decisions land before the day starts), competitor prices, shopper reaction beyond the simulator's own assumption."""
import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import agent_service, ai_hook, approver, equalize, price_run, proof, runner   # noqa: E402


def load_ctx(run: str, base_url: str):
    ns = argparse.Namespace(run=run, base_url=base_url, seed=21, profile="smoke", policy="off", calibration=None, calib_weight=0.5)
    return runner._load(ns)


def warehouses(ctx, ck):
    return [b["warehouse_id"] for b in ctx.state["companies"][ck]["branches"].values() if "warehouse_id" in b]


def set_policy(ctx, hard: float, soft: float):
    for ck in sorted(ctx.cmap):
        ctx.driver.set_pricing_policy(ctx.owner(ck), "Autonomous", hard, soft, 50, 6, list_price_auto_approve=False)


def clear_old_proposals(ctx):
    n = 0
    for ck in sorted(ctx.cmap):
        owner = ctx.owner(ck)
        for r in ctx.driver.list_price_changes(owner, status="PendingApproval"):
            ctx.driver.reject_list_price(owner, r["id"], "showcase reset: older proposal")
            n += 1
    return n


def price_snapshot(ctx, hooks):
    """{(company, product code): price} as PesoWeb has it now, plus names."""
    out = {}
    for ck in sorted(ctx.cmap):
        owner = ctx.owner(ck)
        for p in price_run.browse(ctx.driver, owner, warehouses(ctx, ck)[0]):
            info = hooks._catalog.get(p["id"])
            if info:
                out[(ck, info["code"])] = {"name": info["name"], "price": p["price"], "cost": p["cost"], "perishable": bool(info["expiry"])}
    return out


def ai_pricing_flow(ctx, hooks, limit: int, fix_limit: int, seed: int, log=print) -> dict:
    drv = ctx.driver
    model = json.loads((ctx.run_dir / "model.json").read_text(encoding="utf-8"))
    summary = {"proposed": 0, "waiting": 0, "refused": 0, "margin_fixes": 0, "approved": 0, "edited": 0, "rejected": 0, "stale": 0, "failed": 0}
    for ck in sorted(ctx.cmap):
        owner = ctx.owner(ck)
        whs = warehouses(ctx, ck)
        status, body = drv._call("POST", "/api/ai/control/run/Pricing", owner.token, raw=True)
        if status != 202:
            raise RuntimeError(f"{ck}: could not request an AI Pricing run: {status} {body}")
        runner_ = agent_service.AgentRunner(drv, owner, {"Pricing": agent_service.pricing_handler(drv, owner, whs, model, limit, fix_limit)}, log=lambda *_: None)
        done = runner_.poll_once()
        log(f"  {ck}: {done[0]['summary'] if done and 'summary' in done[0] else done}")
        last = {s["key"]: s for s in drv._call("GET", "/api/ai/control", owner.token)}["Pricing"]["lastRun"]
        if last["status"] != "Done":
            raise RuntimeError(f"{ck}: AI Pricing run ended {last['status']}: {last['summary']}")
        queue = drv._call("GET", "/api/Pricing/Approvals", owner.token)["items"]
        summary["waiting"] += len(queue)
        summary["margin_fixes"] += sum(1 for i in queue if i.get("confidence") == "rule")
        out = approver.work_queue(drv, owner, seed, approver.ApproverStyle())
        for k in ("approved", "edited", "rejected", "stale", "failed"):
            summary[k] += out[k]
        log(f"  {ck}: approver decided {out['approved']} approved, {out['edited']} half-step, {out['rejected']} rejected, {out['stale']} stale, {out['failed']} failed")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-run", default="real2")
    ap.add_argument("--base-run", default="real3")
    ap.add_argument("--day", type=int, default=201)
    ap.add_argument("--hard", type=float, default=5.0)
    ap.add_argument("--soft", type=float, default=10.0)
    ap.add_argument("--limit", type=int, default=15, help="most profit-based price proposals per company")
    ap.add_argument("--fix-limit", type=int, default=40, help="most margin fixes per company")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    args = ap.parse_args(argv)

    print(f"Showcase: {args.ai_run} (AI) against {args.base_run} (no AI), trial day {args.day}, margin floors {args.hard:g}% hard / {args.soft:g}% soft")
    ctx_ai, ctx_base = load_ctx(args.ai_run, args.base_url), load_ctx(args.base_run, args.base_url)
    hooks_ai = ai_hook.AiHooks(ctx_ai, agent_on=True)
    hooks_base = ai_hook.AiHooks(ctx_base, agent_on=False)
    hooks_ai.load_model()
    hooks_base.load_model()

    print("1. Policy and a clean inbox")
    set_policy(ctx_ai, args.hard, args.soft)
    set_policy(ctx_base, args.hard, args.soft)
    print(f"   cleared {clear_old_proposals(ctx_ai)} older proposals")
    before = price_snapshot(ctx_ai, hooks_ai)

    print("2. AI Pricing run, then the simulated approver")
    flow = ai_pricing_flow(ctx_ai, hooks_ai, args.limit, args.fix_limit, args.seed, log=print)

    after = price_snapshot(ctx_ai, hooks_ai)
    changes = []
    for key, b in before.items():
        a = after[key]
        if abs(a["price"] - b["price"]) > 0.005:
            changes.append({"company": key[0], "name": b["name"], "from": b["price"], "to": a["price"], "cost": b["cost"],
                            "pct": round((a["price"] - b["price"]) / b["price"] * 100, 1), "perishable": b["perishable"],
                            "margin_before_pct": round((b["price"] - b["cost"]) / b["price"] * 100, 1), "margin_after_pct": round((a["price"] - b["cost"]) / a["price"] * 100, 1)})
    # shoppers react to the price they see now, relative to the catalog price the world was built with
    ref_prices = {(i["company"], i["code"]): i["list_price"] for i in hooks_ai._catalog.values()}
    for key, a in after.items():
        r = a["price"] / ref_prices[key]
        if abs(r - 1.0) > 1e-9:
            hooks_ai.price_over[key] = r
    print(f"   {len(changes)} list prices changed in PesoWeb; {sum(1 for c in changes if c['perishable'])} are perishables")

    print("3. Trial day: short-dated lots and the day's shoppers (stock and lot sizes equalised in both worlds first)")
    equalize.align_rates(hooks_base, hooks_ai)
    for c, h in ((ctx_ai, hooks_ai), (ctx_base, hooks_base)):
        equalize.clear_leftover_lots(c, h)
        equalize.top_up_stock(c, h, tag=f"top{args.day}")
    hooks_ai.agent_on = True
    stats_ai = hooks_ai.run_trial(args.day)
    hooks_base.agent_on = False
    stats_base = hooks_base.run_trial(args.day)
    m_ai, m_base = proof.metrics_from(stats_ai), proof.metrics_from(stats_base)

    diff = {k: m_ai[k] - m_base[k] for k in ("waste_pesos", "revenue", "margin", "net", "units")}
    result = {"ai_run": args.ai_run, "base_run": args.base_run, "day": args.day, "floors": {"hard": args.hard, "soft": args.soft},
              "pricing_flow": flow, "list_prices_changed": len(changes), "changes": changes, "ai": m_ai, "base": m_base, "difference": diff}
    (runner.RUNS / "showcase.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    pct = lambda a, b: (a - b) / b * 100 if b else 0.0
    L = [f"# PesoProfit showcase: {args.ai_run} (AI) against {args.base_run} (no AI), trial day {args.day}", "",
         f"Margin floors {args.hard:g}% hard / {args.soft:g}% soft. Real catalog, 5 companies x 2 branches. Same shoppers, same shelf stock and same short-dated lots in both worlds (checked by an A/A run with no AI: zero difference).", "",
         f"**AI Pricing flow:** {flow['waiting']} proposals reached the Approval Center ({flow['margin_fixes']} margin fixes, the rest profit-based); the simulated approver approved {flow['approved']}, approved half the step on {flow['edited']}, rejected {flow['rejected']} ({flow['stale']} went stale, {flow['failed']} failed). "
         f"{len(changes)} list prices changed in PesoWeb, {sum(1 for c in changes if c['perishable'])} of them perishables.", "",
         "| | No AI | With AI | Difference |", "|---|---|---|---|"]
    for label, k in (("Revenue", "revenue"), ("Gross margin", "margin"), ("Waste (pesos)", "waste_pesos"), ("Net (margin minus waste)", "net"), ("Units sold", "units")):
        share = "" if k == "net" else f" ({pct(m_ai[k], m_base[k]):+.1f}%)"      # a percentage of a negative number misleads
        L.append(f"| {label} | {m_base[k]:,.0f} | {m_ai[k]:,.0f} | {m_ai[k] - m_base[k]:+,.0f}{share} |")
    L += ["", f"Markdowns applied by the agent: {m_ai['markdowns_applied']} (refused by the rules: {m_ai['markdowns_refused']}).", "",
          "Read this carefully: one trial day per world, so the numbers are indicative, not a statistic. How shoppers react to a price change is the simulator's own hidden assumption. "
          "The two effects (new list prices, and markdowns) are not separated here. There is no competitor price feed, and the approver's waiting time is not simulated.", ""]
    L += ["## List-price changes (largest first)", "", "| Company | Product | From | To | Change | Margin before | Margin after |", "|---|---|---|---|---|---|---|"]
    for c in sorted(changes, key=lambda c: -abs(c["pct"]))[:30]:
        L.append(f"| {c['company']} | {c['name'][:36]} | {c['from']:g} | {c['to']:g} | {c['pct']:+.1f}% | {c['margin_before_pct']}% | {c['margin_after_pct']}% |")
    (runner.RUNS / "showcase.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

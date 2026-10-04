"""The proof: the same seeded world played three ways on a short-dated trial day.

    none   no markdowns at all
    fixed  a store rule: 30% off last-day batches at opening (falls back to 20%, 10% if PesoWeb refuses)
    ai     the MissionCommerce markdown agent, hour by hour, inside PesoWeb's guardrails

Each arm gets a fresh world built from the same seed, the same promo-day history, the same lots and the same shoppers;
only the pricing behavior differs. Money outcomes (waste, margin, net) come from PesoWeb's own batch quantities and the
sale totals; the AI's prediction errors come from the recorder. The shopper price response is the simulator's own
assumption, so this shows the mechanism and the guardrails under that assumption, not a real-market lift.

    python -m simpeso.proof --seeds 1-5 --out ../results/proof-smoke.json
"""
import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from . import runner, world
from .ai_hook import AiHooks, FixedRuleHooks
from .driver import PesoWebDriver

ARMS = ("none", "fixed", "ai")
METRICS = ("waste_pesos", "revenue", "margin", "net", "units", "markdowns_applied", "markdowns_refused")


def make_ctx(base_url: str, run: str, seed: int, profile: str, hard: float, soft: float):
    run_dir = runner.RUNS / run
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {"run": run, "seed": seed, "profile": profile, "tag": run, "companies": {},
             "policy": {"mode": "Autonomous", "hard": hard, "soft": soft, "max_discount": 50, "max_changes": 6}}
    plan = world.plan_group(seed, profile)
    drv = PesoWebDriver(base_url, run)
    root = drv.login(os.environ.get("PESOWEB_ROOT_EMAIL", "superadmin@email.com"), os.environ["PESOWEB_ROOT_PASSWORD"])
    return runner.Context(drv, plan, state, run_dir, root)


def metrics_from(stats: dict) -> dict:
    margin = stats["revenue"] - stats["cogs"]
    waste = stats["trial_waste_pesos"]
    return {"waste_pesos": waste, "revenue": stats["revenue"], "margin": margin, "net": margin - waste,
            "units": stats["units"], "markdowns_applied": stats.get("markdowns_applied", 0),
            "markdowns_refused": stats.get("markdowns_refused", 0)}


def run_arm(base_url: str, seed: int, arm: str, profile: str = "smoke", hard: float = 0, soft: float = 5, log=print) -> dict:
    ctx = make_ctx(base_url, f"proof-s{seed}-{arm}", seed, profile, hard, soft)
    runner.build(ctx, log=lambda *_: None)
    hooks = {"none": lambda: AiHooks(ctx, agent_on=False), "fixed": lambda: FixedRuleHooks(ctx),
             "ai": lambda: AiHooks(ctx, agent_on=True)}[arm]()
    hooks.run_history()
    hooks.agent_on = arm == "ai"
    stats = hooks.run_trial()
    out = metrics_from(stats)
    if arm == "ai":
        out["calibration"] = hooks.recorder.calibration()
    log(f"seed {seed} {arm:5s}: waste {out['waste_pesos']:8.0f}  margin {out['margin']:9.0f}  net {out['net']:9.0f}  "
        f"units {out['units']:.0f}  markdowns {out['markdowns_applied']}")
    return out


def summarize(per_seed: dict) -> dict:
    """per_seed: {seed: {arm: metrics}}. Means per arm and paired differences (ai - baseline) with win counts."""
    seeds = sorted(per_seed)
    out = {"seeds": seeds, "arms": {}, "paired": {}}
    for arm in ARMS:
        out["arms"][arm] = {m: statistics.mean(per_seed[s][arm][m] for s in seeds) for m in METRICS}
    for base in ("none", "fixed"):
        row = {}
        for m in ("waste_pesos", "margin", "net", "revenue"):
            diffs = [per_seed[s]["ai"][m] - per_seed[s][base][m] for s in seeds]
            better = (lambda d: d < 0) if m == "waste_pesos" else (lambda d: d > 0)
            row[m] = {"mean_diff": statistics.mean(diffs), "min_diff": min(diffs), "max_diff": max(diffs),
                      "seeds_ai_better": sum(1 for d in diffs if better(d)), "of": len(diffs)}
        out["paired"][f"ai_vs_{base}"] = row
    cals = [per_seed[s]["ai"].get("calibration") for s in seeds if per_seed[s]["ai"].get("calibration", {}).get("resolved")]
    if cals:
        out["calibration"] = {"resolved": sum(c["resolved"] for c in cals),
                              "interval_coverage": statistics.mean(c["interval_coverage"] for c in cals),
                              "predicted_waste_pesos": sum(c["predicted_waste_pesos"] for c in cals),
                              "realized_waste_pesos": sum(c["realized_waste_pesos"] for c in cals),
                              "units_mae": statistics.mean(c["units_mae"] for c in cals),
                              "naive_units_mae": statistics.mean(c["naive_units_mae"] for c in cals)}
    return out


def parse_seeds(text: str) -> list:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.proof")
    ap.add_argument("--seeds", default="1-3")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--profile", default="smoke", choices=sorted(world.PROFILES))
    ap.add_argument("--hard-floor", type=float, default=0)
    ap.add_argument("--soft-floor", type=float, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    per_seed = {}
    for seed in parse_seeds(args.seeds):
        per_seed[seed] = {arm: run_arm(args.base_url, seed, arm, args.profile, args.hard_floor, args.soft_floor) for arm in ARMS}
    result = {"profile": args.profile, "policy": {"hard_floor_pct": args.hard_floor, "soft_floor_pct": args.soft_floor},
              "per_seed": per_seed, "summary": summarize(per_seed),
              "note": "Shopper price response is the simulator's own assumption; this shows mechanism and guardrails, not real-market lift."}
    text = json.dumps(result, indent=2, default=float)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Produce the files the dashboard reads (results/*.json) from real runs.

    PESOWEB_ROOT_PASSWORD=... python scripts/export_results.py --what incident     # needs PesoWeb running
    python scripts/export_results.py --what actions --from-run proof-s1-ai         # sample of agent decisions
    python scripts/export_results.py --what quicksim --device auto                 # aggregated lane

proof-smoke.json comes from `python -m simpeso.proof`."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simpeso import ai_hook, incidents as inc, proof, quicksim, runner, scoring   # noqa: E402

RESULTS = ROOT.parent / "results"
HOW = {
    ("CASH_SHORT", "caught"): "PesoWeb closed the shift with a variance and raised a CASH_VARIANCE exception (unexplained cash variance).",
    ("NEAR_EXPIRY_BATCH", "caught"): "PesoWeb's expiry detection raised an EXPIRY_ALERT for that exact batch.",
    ("UNREPORTED_SHORT_DELIVERY", "undetected"): "PesoWeb has no record of the physical shortfall; no count has looked yet.",
    ("HIDDEN_SHRINK", "undetected"): "Stock left the shelf without a record; no count has looked yet.",
    ("UNREPORTED_SHORT_DELIVERY", "ai_found"): "A risk-ranked stock count came back short after a delivery with no receiving report.",
    ("HIDDEN_SHRINK", "ai_found"): "A risk-ranked stock count came back short on a high-value fast mover.",
}


def incident_demo(base_url: str, seed: int = 21) -> dict:
    run = f"export-incident-s{seed}"
    ctx = proof.make_ctx(base_url, run, seed, "smoke", 0, 5)
    runner.build(ctx, log=lambda *_: None)
    runner.run_day(ctx, 0, log=lambda *_: None)
    steps = []
    card = runner.score_run(ctx).summary()
    steps.append({"label": "PesoWeb alone", **{k: card[k] for k in ("caught", "ai_found", "undetected", "coverage")}})
    for k, label in ((4, "AI counts 4 SKUs per branch"), (8, "AI counts 8 SKUs per branch (every SKU)")):
        ai_hook.find_incidents(ctx, k, log=lambda *_: None)
        card = runner.score_run(ctx).summary()
        steps.append({"label": label, **{kk: card[kk] for kk in ("caught", "ai_found", "undetected", "coverage")}})
    ledger = inc.Ledger.load(ctx.run_dir / "ledger.json")
    rows = []
    for i, o in zip(ledger.incidents, runner.score_run(ctx).outcomes):
        rows.append({"type": i.type, "branch": i.branch, "status": o.status, "how": HOW.get((i.type, o.status), "")})
    return {"seed": seed, "profile": "smoke", "by_budget": steps, "incidents": rows,
            "note": "Ground truth is the simulator's incident ledger; PesoWeb alerts that no incident explains are not counted as findings."}


def actions_sample(run: str, limit: int = 14) -> list:
    path = runner.RUNS / run / "ai_actions.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("type") == "markdown"]
    refused = [r for r in rows if r["status"] != "applied"]
    applied = [r for r in rows if r["status"] == "applied"]
    keep = refused[:4] + applied[:limit - min(4, len(refused))]
    return [{k: r.get(k) for k in ("status", "discount_pct", "code", "explanation", "hour", "warehouse_id")} for r in keep]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", required=True, choices=["incident", "actions", "quicksim"])
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--from-run", default="proof-s1-ai")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--individuals", type=int, default=200_000)
    args = ap.parse_args(argv)
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.what == "incident":
        out, data = RESULTS / "incident-demo.json", incident_demo(args.base_url)
    elif args.what == "actions":
        out, data = RESULTS / "ai-actions-sample.json", actions_sample(args.from_run)
    else:
        out, data = RESULTS / "quicksim.json", quicksim.run(individuals=args.individuals, device=args.device)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build the day report for one simulated run: group -> company -> branch, plus what went wrong and who noticed.

    PESOWEB_ROOT_PASSWORD=... python scripts/day_report.py --run fin3          # writes results/day-report-fin3.json

Numbers come from PesoWeb (group overview as the central company, exceptions as each owner); the incident ledger, scorecard
and AI action log come from the run folder. "Today" is PesoWeb's own clock, so it covers everything this run did today:
the incident day, the learning days and the markdown trial."""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simpeso import incidents as inc, runner, scoring, world   # noqa: E402
from simpeso.driver import PesoWebDriver                       # noqa: E402

RESULTS = ROOT.parent / "results"


def clock(h):
    return f"{int(h):02d}:{int(round((h - int(h)) * 60)):02d}"


def build(run: str, base_url: str) -> dict:
    run_dir = runner.RUNS / run
    state = json.loads((run_dir / "world.json").read_text(encoding="utf-8"))
    plan = world.plan_group(state["seed"], state["profile"])
    drv = PesoWebDriver(base_url, "day-report")
    root = drv.login(os.environ.get("PESOWEB_ROOT_EMAIL", "superadmin@email.com"), os.environ["PESOWEB_ROOT_PASSWORD"])
    overview = drv._call("GET", "/api/Group/Overview", root.token)
    by_tenant = {t["tenantId"]: t for t in overview["tenants"]}

    wh_key, wh_company = {}, {}
    for ck, c in state["companies"].items():
        for bk, b in c["branches"].items():
            if "warehouse_id" in b:
                wh_key[b["warehouse_id"]] = bk
                wh_company[b["warehouse_id"]] = ck
    expansions = {e["branch"]: e for e in plan.expansions}
    cmap = {c.key: c for c in plan.companies}

    companies, exc_by_branch = [], collections.defaultdict(collections.Counter)
    for ck, c in state["companies"].items():
        owner = drv.login(c["owner"]["email"], c["owner"]["password"])
        for e in drv._call("GET", "/api/ai/exceptions?afterId=0&take=1000", owner.token)["exceptions"]:
            if e.get("warehouseId") in wh_key:
                exc_by_branch[e["warehouseId"]][e["type"]] += 1
        t = by_tenant.get(c["owner"]["tenant_id"])
        if not t:
            continue
        branches = []
        for b in t["branches"]:
            key = wh_key.get(b["warehouseId"], str(b["warehouseId"]))
            ex = expansions.get(key)
            branches.append({**b, "key": key, "opened_midrun": f"{clock(ex['hour'])}" if ex else None,
                             "exceptions_by_type": dict(exc_by_branch[b["warehouseId"]])})
        companies.append({"key": ck, "name": cmap[ck].name, "vertical": cmap[ck].vertical, "tenant_id": c["owner"]["tenant_id"],
                          "totals": t["totals"], "branches": branches})

    report = {"run": run, "seed": state["seed"], "profile": state["profile"], "generated_at": overview["generatedAt"],
              "totals": {k: sum(c["totals"][k] for c in companies) for k in
                         ("branches", "salesToday", "transactionsToday", "cashVarianceToday", "expiryAtRiskPesos", "activeMarkdowns", "openExceptions")},
              "companies": companies}

    timeline, incidents_out = [], []
    ledger_path = run_dir / "ledger.json"
    ledger = inc.Ledger.load(ledger_path) if ledger_path.exists() else inc.Ledger()
    if ledger.incidents:
            findings_path = run_dir / "ai_findings.json"
            findings = json.loads(findings_path.read_text(encoding="utf-8")) if findings_path.exists() else []
            rows = []
            for ck in state["companies"]:
                rows += drv._call("GET", "/api/ai/exceptions?afterId=0&take=1000", drv.login(state["companies"][ck]["owner"]["email"], state["companies"][ck]["owner"]["password"]).token)["exceptions"]
            card = scoring.score(ledger.incidents, rows, findings)
            for i, o in zip(ledger.incidents, card.outcomes):
                incidents_out.append({"id": i.id, "type": i.type, "branch": i.branch, "hour": i.hour, "detail": i.detail, "status": o.status})
                timeline.append({"hour": i.hour, "text": f"Injected {i.type.replace('_', ' ').lower()} at {i.branch} ({o.status.replace('_', ' ')})"})
            report["scorecard"] = card.summary()
    for e in plan.expansions:
        timeline.append({"hour": e["hour"], "text": f"{cmap[e['company']].name} opened branch {e['branch']}"})
    actions_path = run_dir / "ai_actions.jsonl"
    actions = []
    if actions_path.exists():
        for line in actions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                a = json.loads(line)
                if a.get("type") == "markdown":
                    actions.append(a)
    per_branch_ai = collections.defaultdict(collections.Counter)
    for a in actions:
        per_branch_ai[wh_key.get(a["warehouse_id"], str(a["warehouse_id"]))][a["status"]] += 1
    for c in report["companies"]:
        for b in c["branches"]:
            b["ai_markdowns"] = dict(per_branch_ai.get(b["key"], {}))
    report["ai_actions"] = {"total": len(actions), "applied": sum(1 for a in actions if a["status"] == "applied"),
                            "refused": sum(1 for a in actions if a["status"] == "refused"),
                            "examples": [{"status": a["status"], "discount_pct": a["discount_pct"], "code": a.get("code"), "hour": a.get("hour"),
                                          "explanation": a.get("explanation")} for a in actions[:8]]}
    report["incidents"] = incidents_out
    report["timeline"] = sorted(timeline, key=lambda t: t["hour"])
    report["note"] = "Sales, cash and exception figures are PesoWeb's own, for everything this run did today on PesoWeb's clock (incident day, learning days, markdown trial)."
    return report


def kind_of(run: str) -> str:
    if run.startswith("proof-"):
        arm = run.rsplit("-", 1)[1]
        return {"none": "Proof arm: no markdown", "fixed": "Proof arm: fixed rule", "ai": "Proof arm: AI agent"}.get(arm, "Proof arm")
    return "Incident day + AI trial world"


def build_all(base_url: str) -> list:
    index = []
    for d in sorted(runner.RUNS.iterdir()):
        if not (d / "world.json").exists():
            continue
        try:
            rep = build(d.name, base_url)
        except Exception as exc:                       # a world whose tenants were purged, etc.
            index.append({"run": d.name, "error": str(exc)[:120]})
            continue
        (RESULTS / f"day-report-{d.name}.json").write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
        t, sc = rep["totals"], rep.get("scorecard")
        index.append({"run": d.name, "kind": kind_of(d.name), "profile": rep["profile"], "seed": rep["seed"], "branches": t["branches"],
                      "salesToday": t["salesToday"], "transactionsToday": t["transactionsToday"], "openExceptions": t["openExceptions"],
                      "activeMarkdowns": t["activeMarkdowns"], "aiMarkdownsApplied": rep["ai_actions"]["applied"],
                      "incidents": sc["injected"] if sc else 0, "coverage": sc["coverage"] if sc else None,
                      "caught": sc["caught"] if sc else None, "aiFound": sc["ai_found"] if sc else None})
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--all", action="store_true", help="every run folder, plus results/reports-index.json")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    args = ap.parse_args(argv)
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.all:
        idx = build_all(args.base_url)
        (RESULTS / "reports-index.json").write_text(json.dumps({"runs": idx}, indent=1, default=float), encoding="utf-8")
        print(f"wrote {len([i for i in idx if 'error' not in i])} day reports and reports-index.json; errors: {[i['run'] for i in idx if 'error' in i]}")
        return 0
    if not args.run:
        ap.error("--run or --all is required")
    out = RESULTS / f"day-report-{args.run}.json"
    out.write_text(json.dumps(build(args.run, args.base_url), indent=1, default=float), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

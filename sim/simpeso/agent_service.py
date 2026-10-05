"""The agent runner: the small always-on program that connects the AI to one company's PesoWeb.

    python -m simpeso.agent_service --run real2 --company c1 --once        # handle what is waiting, then stop
    python -m simpeso.agent_service --run real2 --company c1 --interval 30 # keep polling every 30 seconds

It does what the owner's AI Control screen says, and nothing else:
  * reads the switches (GET /api/ai/settings): a feature that is off is never run;
  * picks up "run now" requests (GET /api/ai/run-requests), marks one running, does the work, reports Done or Failed.
PesoWeb enforces the switch on its side too (a switched-off AI Pricing gets its proposals refused), so a runner that
ignored the switch would still be stopped. Features with no handler here fail the run with a clear message.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def is_enabled(settings: list, feature: str) -> bool:
    row = next((s for s in settings if s["key"] == feature), None)
    return bool(row and row["enabled"])


class AgentRunner:
    def __init__(self, drv, acct, handlers: dict, log=print):
        self.drv, self.acct, self.handlers, self.log = drv, acct, handlers, log

    def settings(self) -> list:
        return self.drv._call("GET", "/api/ai/settings", self.acct.token)

    def poll_once(self) -> list:
        """Handle every waiting run request once. Returns one result row per request."""
        settings = self.settings()
        waiting = self.drv._call("GET", "/api/ai/run-requests?status=Requested", self.acct.token) or []
        results = []
        for req in waiting:
            feature, rid = req["feature"], req["id"]
            if not is_enabled(settings, feature):
                # Starting a run for a switched-off feature makes PesoWeb cancel it and say so.
                self.drv._call("POST", f"/api/ai/run-requests/{rid}/start", self.acct.token, raw=True)
                results.append({"id": rid, "feature": feature, "outcome": "cancelled (switched off)"})
                self.log(f"run {rid} {feature}: switched off, not run")
                continue
            status, body = self.drv._call("POST", f"/api/ai/run-requests/{rid}/start", self.acct.token, raw=True)
            if status != 200:
                results.append({"id": rid, "feature": feature, "outcome": f"could not start ({status})"})
                continue
            handler = self.handlers.get(feature)
            try:
                if handler is None:
                    raise RuntimeError(f"this runner has no handler for {feature}")
                summary, ok = handler(), True
            except Exception as e:                      # report it to the owner instead of dying silently
                summary, ok = f"{type(e).__name__}: {e}", False
            self.drv._call("POST", f"/api/ai/run-requests/{rid}/finish", self.acct.token, json_body={"Ok": ok, "Summary": summary[:490]}, raw=True)
            results.append({"id": rid, "feature": feature, "outcome": "done" if ok else "failed", "summary": summary})
            self.log(f"run {rid} {feature}: {'done' if ok else 'FAILED'}: {summary}")
        return results

    def serve(self, interval: float, stop=lambda: False):
        while not stop():
            self.poll_once()
            time.sleep(interval)


def pricing_handler(drv, acct, warehouse_ids: list, model: dict, limit: int = 8, fix_limit: int = 25):
    """AI Pricing run: look at every product's cost, sales rate and learned price sensitivity, then put the best list-price changes
    into the Approval Center. Nothing is applied here; a person (or the tenant's own auto-approve limits) decides."""
    from . import price_run

    def run() -> str:
        _, sugg, _ = price_run.suggestions_for(drv, acct, warehouse_ids, model)
        sent = price_run.propose_top(drv, acct, warehouse_ids[0], sugg, limit, fix_limit)
        waiting = sum(1 for r in sent if r["status"] == 202)
        applied = sum(1 for r in sent if r["status"] == 200)
        refused = sum(1 for r in sent if r["status"] == 422)
        fixes = sum(1 for r in sent if r["kind"] == "margin fix")
        return f"proposed {len(sent)} price changes ({fixes} margin fixes): {waiting} waiting in the Approval Center, {applied} auto-approved, {refused} refused by a rule"

    return run


def main(argv=None) -> int:
    from . import runner
    from .driver import PesoWebDriver
    ap = argparse.ArgumentParser(prog="simpeso.agent_service")
    ap.add_argument("--run", required=True, help="a simulated world under sim/runs (gives the company logins and the learned model)")
    ap.add_argument("--company", default="c1")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--limit", type=int, default=8, help="most price proposals per Pricing run")
    args = ap.parse_args(argv)
    run_dir = runner.RUNS / args.run
    state = json.loads((run_dir / "world.json").read_text(encoding="utf-8"))
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    comp = state["companies"][args.company]
    drv = PesoWebDriver(args.base_url, "agent-service")
    acct = drv.login(comp["owner"]["email"], comp["owner"]["password"])
    whs = [b["warehouse_id"] for b in comp["branches"].values() if "warehouse_id" in b]
    agent = AgentRunner(drv, acct, {"Pricing": pricing_handler(drv, acct, whs, model, args.limit)})
    if args.once:
        agent.poll_once()
        return 0
    print(f"agent runner for {args.run}/{args.company} polling every {args.interval:g}s; Ctrl+C to stop")
    try:
        agent.serve(args.interval)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

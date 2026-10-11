"""Live check of AI Insight: ask PesoWeb for a run, let the agent write the notes, read them back as the Intelligent Hub does.

    python scripts/insight_check.py [email] [password]        (default: the 520 Minimart super user; a company with some AI results)
It uses a language model only if one is configured in the environment (see ai/missionai/llm.py); otherwise the standard wording.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso import agent_service                   # noqa: E402
from simpeso.driver import PesoWebDriver            # noqa: E402
from missionai import insight, llm                  # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    email = sys.argv[1] if len(sys.argv) > 1 else "superuser@520minimart.test"
    password = sys.argv[2] if len(sys.argv) > 2 else "Abc123##"
    drv = PesoWebDriver(BASE, "insight-check")
    a = drv.login(email, password)
    branches = drv._call("GET", "/api/ai/branch-settings", a.token) or []
    whs = [b["warehouseId"] for b in branches]
    print("wording:", llm.describe())

    print("1. AI Insight can be run")
    states = {s["feature"] if "feature" in s else s.get("key"): s for s in drv._call("GET", "/api/ai/control", a.token)}
    row = states.get("Insight") or {}
    check(row.get("buildState", row.get("BuildState")) == "Built" and row.get("canRun", row.get("CanRun")), "AI Insight is built and has a Run now")
    st, body = drv._call("POST", "/api/ai/control/run/Insight", a.token, raw=True)
    check(st in (200, 202), f"a run was requested ({st})")

    print("2. The agent writes the notes")
    agent = agent_service.AgentRunner(drv, a, {"Insight": agent_service.insight_handler(drv, a, whs, wording=llm.from_env())}, log=lambda *x: None)
    res = next((r for r in agent.poll_once() if r["feature"] == "Insight"), {})
    check(res.get("outcome") == "done", "the run finished: " + str(res.get("summary")))

    print("3. The Hub reads them back")
    notes = drv._call("GET", "/api/ai/insights", a.token) or []
    check(len(notes) > 0, f"{len(notes)} note(s) are listed")
    kinds = {n["kind"] for n in notes}
    print("      kinds:", sorted(kinds))
    check(all(n["headline"] and n["body"] for n in notes), "every note has a headline and a body")
    check(all(n["source"] in ("template", "model") for n in notes), "every note says whether it was reworded")
    for n in notes[:4]:
        print(f"      [{n['kind']}] {n['headline']}\n         {n['body']}")

    print("4. Every figure in a note is a figure in the data")
    sell = {f"SellFast:{r['id']}": r for r in drv.count_suggestions(a, "Open", "SellFast")}
    bad = 0
    for n in notes:
        r = sell.get(n["refKey"])
        if r and n["source"] == "model":
            facts = {k: r.get(k) for k in ("product", "branch", "daysLeft", "batchQty", "ratePerDay", "unitsAtRisk", "valueAtRiskAtCost",
                                          "suggestedDiscountPct", "suggestedPrice", "proposalStatus")}
            if not insight.valid_wording(n["body"], facts, insight.template("SellFast", facts)[1]):
                bad += 1
    check(bad == 0, "no reworded note contains a figure that is not in the data")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

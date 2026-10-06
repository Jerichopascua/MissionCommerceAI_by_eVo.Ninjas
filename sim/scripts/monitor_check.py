"""Live check of AI Monitoring on a fresh throwaway shop: run-now, a cash difference far above the shop's usual becomes an alert,
the rule's role and switch apply, repeats update instead of duplicating, and the feature switch is enforced.

    python scripts/monitor_check.py
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso import agent_service                   # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    run = "mon-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Monitor Store", "Demo", "Owner", f"{run}@mon.test", "Hub!123456")
    wh = a.warehouse_id
    drv.setup_basics(a)
    quiet = lambda *x: None
    agent = agent_service.AgentRunner(drv, a, {"Monitoring": agent_service.monitoring_handler(drv, a, [wh])}, log=quiet)

    print("1. The feature")
    ctl = {f["key"]: f for f in drv._call("GET", "/api/ai/control", a.token)}
    check(ctl["Monitoring"]["canRun"] and ctl["Monitoring"]["buildState"] == "Built", "AI Monitoring can be run now")
    rules = {r["key"]: r for r in drv._call("GET", "/api/ai/hub/rules", a.token)}
    check(rules["AiAnomaly"]["externallyFed"] and rules["AiAnomaly"]["role"] == "Owner", "the rule 'Unusual activity found by AI' exists, for the Owner, with no limit to set")

    print("2. A quiet shop says nothing")
    st, o = drv._call("POST", "/api/ai/control/run/Monitoring", a.token, raw=True)
    res = agent.poll_once()
    mon = next((r for r in res if r["feature"] == "Monitoring"), {})
    check(st == 202 and mon.get("outcome") == "done" and "0 unusual" in mon.get("summary", ""), "a run on a shop with no history finds nothing unusual: " + mon.get("summary", ""))

    print("3. A cash difference far above the shop's usual")
    for _ in range(6):
        sid = drv.open_shift(a, wh, "T1", 100)
        drv.close_shift(a, sid, 100)                    # counted what it opened with: no difference
    sid = drv.open_shift(a, wh, "T1", 500)
    drv.close_shift(a, sid, 200)                        # 300 short
    drv._call("POST", "/api/ai/control/run/Monitoring", a.token, raw=True)
    res = agent.poll_once()
    mon = next((r for r in res if r["feature"] == "Monitoring"), {})
    check(mon.get("outcome") == "done" and "1 new" in mon.get("summary", ""), "the run opens one alert: " + mon.get("summary", ""))
    tasks = drv.hub_tasks(a)
    mine = [x for x in tasks["items"] if x["kind"] == "Alert" and "cash shift" in str(x)]
    check(len(mine) == 1, "the alert is in My tasks")
    check("300" in str(mine) and "short" in str(mine) and "usual" in str(mine), "it says what was seen: a shift closed 300 short against the usual")

    print("4. A repeat updates, never duplicates")
    drv._call("POST", "/api/ai/control/run/Monitoring", a.token, raw=True)
    res = agent.poll_once()
    mon = next((r for r in res if r["feature"] == "Monitoring"), {})
    check("0 new" in mon.get("summary", "") and "1 still open" in mon.get("summary", ""), "the next run keeps the same alert: " + mon.get("summary", ""))

    print("5. The rule and the switch apply")
    st, _ = drv._call("PUT", "/api/ai/hub/rules/AiAnomaly", a.token, json_body={"enabled": False, "threshold": 0, "role": "Owner", "severity": "Watch", "notifyEmail": False}, raw=True)
    drv._call("POST", "/api/ai/control/run/Monitoring", a.token, raw=True)
    res = agent.poll_once()
    mon = next((r for r in res if r["feature"] == "Monitoring"), {})
    check(st == 200 and "1 closed" in mon.get("summary", ""), "with the rule switched off the alert closes and none opens: " + mon.get("summary", ""))
    drv._call("PUT", "/api/ai/control/Monitoring", a.token, json_body={"enabled": False})
    st, o = drv.post_monitor_findings(a, [{"key": "x", "warehouse_id": wh, "kind": "Cash", "message": "m", "value": 1}])
    check(st == 422 and o.get("code") == "AI_FEATURE_OFF", "with AI Monitoring switched off PesoWeb refuses findings")
    drv._call("PUT", "/api/ai/control/Monitoring", a.token, json_body={"enabled": True})

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

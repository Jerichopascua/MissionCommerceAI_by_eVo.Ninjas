"""Live check of the AI Control switches and run-now requests on a fresh throwaway shop. Uses only the local PesoWeb.

    python scripts/ai_control_check.py
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import agent_service              # noqa: E402
from simpeso.driver import PesoWebDriver       # noqa: E402
from simpeso.verticals import ProductSpec      # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def main() -> int:
    run = "aic-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("AI Control Check Store", "Demo", "Owner", f"{run}@aic.test", "Aic!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pid = drv.add_product(a, ProductSpec("AIC-1", "Test item", "Grocery", 60, 100, False), cat, basics)
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)

    print("1. The owner's screen lists the six AI features")
    states = drv._call("GET", "/api/ai/control", a.token)
    by = {s["key"]: s for s in states}
    check(len(states) == 6 and all(s["enabled"] for s in states), "six features, all on for a company that never touched the switch")
    check(by["Pricing"]["buildState"] == "Built" and by["Replenish"]["buildState"] == "Built" and by["CustomerMission"]["buildState"] == "Built" and by["Insight"]["buildState"] == "Partial", "each says whether it is built")

    print("2. Switching AI Pricing off stops AI proposals, not a person's")
    st, o = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 103, "Source": "Ai", "Confidence": "learned"}, raw=True)
    check(st == 202, "with it on, an AI proposal waits for approval")
    drv._call("PUT", "/api/ai/control/Pricing", a.token, json_body={"enabled": False})
    st, o = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 104, "Source": "Ai"}, raw=True)
    check(st == 422 and o.get("code") == "AI_FEATURE_OFF", "with it off, an AI list-price proposal is refused AI_FEATURE_OFF")
    st, o = drv._call("POST", "/api/Pricing/Markdown", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "BatchId": 1, "NewPrice": 90, "Source": "Ai"}, raw=True)
    check(st == 422 and o.get("code") == "AI_FEATURE_OFF", "and so is an AI markdown")
    st, o = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 104, "Source": "Manual"}, raw=True)
    check(st == 202, "a person's own proposal is not affected")
    st, o = drv._call("POST", "/api/ai/control/run/Pricing", a.token, raw=True)
    check(st == 409, "a run cannot be requested while it is off")
    check({s["key"]: s for s in drv._call("GET", "/api/ai/control", a.token)}["LossPrevention"]["enabled"], "other features are untouched")

    print("3. A run request goes through the agent runner")
    drv._call("PUT", "/api/ai/control/Pricing", a.token, json_body={"enabled": True})
    st, o = drv._call("POST", "/api/ai/control/run/Pricing", a.token, raw=True)
    rid = o.get("id")
    check(st == 202, "a run is requested")
    st2, _ = drv._call("POST", "/api/ai/control/run/Pricing", a.token, raw=True)
    check(st2 == 409, "a second request while one waits is refused")
    st3, _ = drv._call("POST", "/api/ai/control/run/Insight", a.token, raw=True)
    check(st3 == 409, "a feature with nothing to run cannot be run")
    ran = []
    agent = agent_service.AgentRunner(drv, a, {"Pricing": lambda: ran.append(1) or "proposed 2 price changes"}, log=lambda *_: None)
    out = agent.poll_once()
    check(ran == [1] and out and out[0]["outcome"] == "done", "the runner picks it up and does the work")
    last = {s["key"]: s for s in drv._call("GET", "/api/ai/control", a.token)}["Pricing"]
    check(last["lastRun"]["status"] == "Done" and "proposed 2" in last["lastRun"]["summary"] and last["openRun"] is None, "the screen shows the finished run and its summary")

    print("4. Switching off cancels a run nobody started")
    st, o = drv._call("POST", "/api/ai/control/run/Pricing", a.token, raw=True)
    drv._call("PUT", "/api/ai/control/Pricing", a.token, json_body={"enabled": False})
    last = {s["key"]: s for s in drv._call("GET", "/api/ai/control", a.token)}["Pricing"]
    check(last["lastRun"]["status"] == "Cancelled" and last["openRun"] is None, "the waiting run is cancelled")
    ran.clear()
    check(agent.poll_once() == [] and ran == [], "the runner has nothing to do")

    print("5. Per-branch AI settings")
    branches = drv._call("GET", "/api/ai/branch-settings", a.token)
    check(len(branches) >= 1 and all(b["pricingEnabled"] and b["clearanceStartHour"] is None for b in branches), "branches start with AI markdowns allowed at any hour")
    wh_id = branches[0]["warehouseId"]
    drv._call("PUT", "/api/ai/control/Pricing", a.token, json_body={"enabled": True})
    drv._call("PUT", f"/api/ai/branch-settings/{wh_id}", a.token, json_body={"PricingEnabled": False})
    st, o = drv._call("POST", "/api/Pricing/Markdown", a.token, json_body={"WarehouseId": wh_id, "ProductId": pid, "BatchId": 1, "NewPrice": 90, "Source": "Ai"}, raw=True)
    check(st == 422 and o.get("code") == "AI_BRANCH_OFF", "an AI markdown at a branch that is switched off is refused AI_BRANCH_OFF")
    drv._call("PUT", f"/api/ai/branch-settings/{wh_id}", a.token, json_body={"PricingEnabled": True, "ClearanceStartHour": 23})
    st, o = drv._call("POST", "/api/Pricing/Markdown", a.token, json_body={"WarehouseId": wh_id, "ProductId": pid, "BatchId": 1, "NewPrice": 90, "Source": "Ai"}, raw=True)
    check(st != 422 or o.get("code") != "AI_BRANCH_OFF", "a start hour does not report the branch as off")
    st, _ = drv._call("PUT", f"/api/ai/branch-settings/{wh_id}", a.token, json_body={"PricingEnabled": True, "ClearanceStartHour": 24}, raw=True)
    check(st == 400, "a start hour outside the day is refused")
    st, _ = drv._call("PUT", "/api/ai/branch-settings/99999999", a.token, json_body={"PricingEnabled": True}, raw=True)
    check(st == 400, "an unknown branch is refused")
    st, _ = drv._call("GET", "/api/ai/settings-overview", a.token, raw=True)
    check(st == 403, "the all-companies view is closed to a company owner")
    ov = drv._call("GET", "/api/ai/hub/overview", a.token)
    check(len(ov["tenants"]) == 1, "the hub overview shows only the owner's own company")

    print("6. Bad input")
    st, _ = drv._call("PUT", "/api/ai/control/Nonsense", a.token, json_body={"enabled": True}, raw=True)
    check(st == 400, "an unknown feature is refused")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

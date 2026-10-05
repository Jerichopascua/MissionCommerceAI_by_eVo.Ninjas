"""Browse a company's products through PesoWeb's own API and turn the price advisor's suggestions into guarded proposals.

Shared by scripts/price_advice.py (suggestions only) and the agent runner (propose into the Approval Center)."""
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[2] / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from missionai import price_advisor as pa          # noqa: E402
from missionai.demand import DemandModel           # noqa: E402

PRIOR_BETA = -1.3
MIN_OBSERVATIONS_TO_CALL_LEARNED = 3


def browse(drv, acct, warehouse_id) -> list:
    out, page = [], 1
    while True:
        r = drv._call("GET", f"/api/Inventory/Products?warehouse={warehouse_id}&page={page}&pageSize=250", acct.token)
        rows = r.get("data", [])
        out += [{"id": x["id"], "name": x["productName"], "category": x["categoryName"], "cost": float(x["cost"]), "price": float(x["price"]),
                 "stock": float(x.get("quantity") or 0), "perishable": bool(x.get("monitorExpiry"))} for x in rows]
        if len(out) >= r.get("recordsTotal", 0) or not rows:
            return out
        page += 1


def demand_model(model: dict) -> DemandModel:
    dm = DemandModel(prior_beta=PRIOR_BETA)
    for c, o in model.get("observations", {}).items():
        dm._obs[c] = [tuple(x) for x in o]
    for c, e in model.get("estimates", {}).items():
        dm._estimates[c] = [tuple(x) for x in e]
    return dm


def suggestions_for(drv, acct, warehouse_ids: list, model: dict, step_pct: int = pa.DEFAULT_STEP_PCT):
    """Returns (products, suggestions, policy). Sales rates and the learned price sensitivity come from the saved model."""
    products = browse(drv, acct, warehouse_ids[0])
    policy = drv.pricing_policy(acct)
    rates = {}
    for k, v in model["rates"].items():
        wh, pid = (int(x) for x in k.split(":"))
        if wh in warehouse_ids:
            rates[pid] = rates.get(pid, 0.0) + float(v)
    dm = demand_model(model)

    def beta_for(cat):
        learned = len(dm._obs.get(cat, [])) >= MIN_OBSERVATIONS_TO_CALL_LEARNED or bool(dm._estimates.get(cat))
        return (dm.beta(cat), "learned") if learned else (PRIOR_BETA, "assumed")

    return products, pa.advise(products, rates, beta_for, policy, step_pct), policy


def propose_top(drv, acct, warehouse_id: int, suggestions: list, limit: int) -> list:
    """Send the largest-gain raise/lower suggestions as list-price proposals. Returns one row per attempt with PesoWeb's answer."""
    # Skip products that already have a proposal waiting, so repeated runs do not pile up duplicates in the Approval Center.
    waiting = {r["productId"] for r in drv.list_price_changes(acct, status="PendingApproval")}
    acts = sorted([s for s in suggestions if s.status in ("raise", "lower") and s.product_id not in waiting], key=lambda s: -s.profit_gain_per_day)[:limit]
    out = []
    for s in acts:
        status, body = drv.propose_list_price(
            acct, warehouse_id, s.product_id, s.suggested_price, reason=s.reason, prediction_ref=f"advice-{s.product_id}-{s.suggested_price:g}",
            confidence=s.beta_source, expected_gain_per_day=round(s.profit_gain_per_day, 2),
            expected_gain_conservative_per_day=round(max(0.0, s.profit_gain_if_more_sensitive), 2), evidence=f"price sensitivity {s.beta:.2f} ({s.beta_source})")
        out.append({"product": s.name, "from": s.price, "to": s.suggested_price, "status": status, "code": (body or {}).get("code")})
    return out

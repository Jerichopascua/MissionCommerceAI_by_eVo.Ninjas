"""MarkdownAgent: each tick (an hour of the trading day) it looks at every branch's at-risk batches, decides with the
optimizer, writes the prediction down, and posts the markdown to PesoWeb as source=Ai. PesoWeb enforces the guardrails
and the autonomy mode; the agent never retries a refusal at a lower price and never tries to get around one.

client interface (the sim's PesoWebDriver adapter implements it):
    policy() -> dict                                   Pricing/Policy
    expiry_batches(warehouse_id) -> list[dict]         Expiry/Risk batches (camelCase)
    markdown(warehouse_id, product_id, batch_id, new_price, reason, prediction_ref) -> (status_code, body)
product_info(product_id) -> {"category", "list_price", "discount_pct", "name"}   the tenant's own catalog
base_per_day(warehouse_id, product_id) -> float | None                           units/day at list price, from sales"""
from . import explain as explain_mod
from .optimizer import Batch, choose

AT_RISK = ("ExpiringSoon", "Critical")
MAX_HORIZON_DAYS = 3


class MarkdownAgent:
    def __init__(self, client, model, recorder, product_info, base_per_day, explainer=None, endpoint=None, not_before_hour=None):
        self.client, self.model, self.recorder = client, model, recorder
        self.not_before_hour = not_before_hour      # the owner's clearance window: no markdown before this hour
        self.product_info, self.base_per_day = product_info, base_per_day
        self.explainer = explainer or (lambda d, o: explain_mod.explain(d, o, endpoint))
        self.applied = {}        # (warehouse, batch) -> discount currently in force
        self.predictions = {}    # (warehouse, batch) -> prediction id (one per batch, made at the first markdown)
        self.refused = set()     # (warehouse, batch, discount) PesoWeb already refused
        self.log = []

    def tick(self, hour: float, warehouse_ids) -> list:
        actions = []
        if self.not_before_hour is not None and hour < self.not_before_hour:
            return actions
        policy = self.client.policy()
        if not policy.get("configured", True) or str(policy.get("autonomyMode", "Off")).lower() == "off":
            return [{"type": "skip", "reason": "pricing autonomy is off"}]
        policy = {"maxDiscountPct": policy.get("maxDiscountPct", 0), "hardMarginFloorPct": policy.get("hardMarginFloorPct", 0),
                  "softMarginFloorPct": policy.get("softMarginFloorPct", 0), "autonomyMode": policy.get("autonomyMode")}
        for wh in warehouse_ids:
            rows = [r for r in self.client.expiry_batches(wh)
                    if r.get("status") in AT_RISK and float(r.get("qtyOnHand", 0)) > 0 and 1 <= int(r["daysLeft"]) <= MAX_HORIZON_DAYS]
            rows.sort(key=lambda r: (r["productId"], r["daysLeft"]))
            ahead = {}
            for r in rows:
                info = self.product_info(r["productId"])
                rate = self.base_per_day(wh, r["productId"])
                queued = ahead.get(r["productId"], 0.0)
                ahead[r["productId"]] = queued + float(r["qtyOnHand"])
                if not info or not rate:
                    continue
                key = (wh, r["batchId"])
                batch = Batch(wh, r["productId"], r["batchId"], info["category"], float(r["qtyOnHand"]), float(r["unitCost"]),
                              float(info["list_price"]), float(max(1, int(r["daysLeft"]))), float(rate),
                              float(info.get("discount_pct", 0)), queued, info.get("name", ""))
                decision = choose(batch, policy, self.model, hour)
                current = self.applied.get(key, 0)
                if decision.discount_pct <= current or (key[0], key[1], decision.discount_pct) in self.refused:
                    continue
                actions.append(self._post(key, decision, hour))
        self.log.extend(actions)
        return actions

    def _post(self, key, decision, hour) -> dict:
        wh, batch_id = key
        pid = self.predictions.get(key)
        if pid is None:
            pid = self.recorder.record(decision, at=f"hour {hour}")
            self.predictions[key] = pid
        b = decision.batch
        status, body = self.client.markdown(wh, b.product_id, batch_id, decision.new_price, decision.reason, pid)
        code = (body or {}).get("code") or (body or {}).get("Code")
        outcome = {"type": "markdown", "warehouse_id": wh, "batch_id": batch_id, "product_id": b.product_id,
                   "discount_pct": decision.discount_pct, "new_price": decision.new_price, "prediction": pid,
                   "http": status, "code": code, "hour": hour}
        if status == 200:
            outcome["status"] = "applied"
            self.applied[key] = decision.discount_pct
        elif status == 202:
            outcome["status"] = "pending"
            outcome["price_change_id"] = (body or {}).get("priceChangeId")
            self.refused.add((wh, batch_id, decision.discount_pct))     # do not re-propose while it waits
        else:
            outcome["status"] = "refused"
            self.refused.add((wh, batch_id, decision.discount_pct))
        outcome["explanation"] = self.explainer(decision, outcome)
        return outcome

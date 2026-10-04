"""Plain-words explanations. The LLM only words a decision that the model and optimizer already made; it is never in
the decision path. With no endpoint (or on any failure) a template sentence is returned, so output never depends on a GPU."""
import json
import urllib.request

REFUSALS = {
    "BELOW_HARD_FLOOR": "it would price the batch below the hard margin floor",
    "EXCEEDS_MAX_DISCOUNT": "it exceeds the maximum discount in the tenant's policy",
    "TOO_MANY_CHANGES": "this product already had the maximum number of price changes this hour",
    "AUTONOMY_OFF": "pricing autonomy is off for this tenant",
    "NO_COST": "the batch has no known unit cost",
    "BELOW_SOFT_FLOOR": "it is below the soft margin floor and needs approval",
    "APPROVAL_MODE": "this tenant requires approval for every markdown",
}


def template(decision, outcome: dict = None) -> str:
    b = decision.batch
    name = b.name or f"product {b.product_id}"
    if decision.discount_pct == 0:
        return f"No markdown for {name} (batch {b.batch_id}): {decision.reason}."
    text = (f"{decision.discount_pct:g}% off {name} (batch {b.batch_id}, {b.qty:g} units, {b.days_left:g} day(s) left): "
            f"{decision.reason}. Prediction: {decision.mean_units:.0f} units "
            f"({decision.lo_units:.0f} to {decision.hi_units:.0f}), about {decision.waste_pesos:.0f} pesos wasted.")
    if outcome:
        status, code = outcome.get("status"), outcome.get("code")
        if status == "refused":
            text += f" PesoWeb refused it because {REFUSALS.get(code, 'a guardrail applies')} ({code})."
        elif status == "pending":
            text += " It is waiting for approval."
    return text


def explain(decision, outcome: dict = None, endpoint: str = None, model: str = "default", timeout: float = 4.0) -> str:
    base = template(decision, outcome)
    if not endpoint:
        return base
    try:
        body = json.dumps({"model": model, "max_tokens": 80, "temperature": 0.2, "messages": [
            {"role": "system", "content": "Rewrite the retail pricing note in one plain sentence a store manager understands. Keep every number. Do not add facts."},
            {"role": "user", "content": base}]}).encode("utf-8")
        req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = json.loads(resp.read())["choices"][0]["message"]["content"].strip()
        return text or base
    except Exception:
        return base

"""Markdown decision for one at-risk batch.

For each discount on a bounded ladder the demand model predicts the units that will sell before the batch expires.
Value of a step = expected revenue minus the batch's sunk cost, which equals margin on the units sold minus the
write-off of the units left at expiry. The best step wins, but only if it beats "no markdown" by a real margin.
Guardrails here mirror PesoWeb's (all on NET price); PesoWeb still enforces them and is the authority."""
from dataclasses import dataclass, field

LADDER = (0, 10, 20, 30, 40, 50)
MIN_GAIN_PESOS = 1.0
MIN_GAIN_SHARE = 0.01


@dataclass
class Batch:
    warehouse_id: int
    product_id: int
    batch_id: int
    category: str
    qty: float
    unit_cost: float
    list_price: float               # list price before the product's own discount
    days_left: float                # includes today
    base_per_day: float             # units per day at list price (estimated from sales)
    product_discount_pct: float = 0.0
    prior_qty: float = 0.0          # units of the same product that expire sooner: FEFO sells them first
    name: str = ""


@dataclass
class Decision:
    batch: Batch
    discount_pct: float
    new_price: float                # base price to send to PesoWeb (list price after the markdown)
    net_price: float
    mean_units: float
    lo_units: float
    hi_units: float
    margin: float
    waste_pesos: float
    baseline_units: float           # prediction with no markdown
    baseline_waste_pesos: float
    value_gain: float
    reason: str
    blocked: list = field(default_factory=list)


def net(list_price: float, product_discount_pct: float) -> float:
    return list_price * (1 - product_discount_pct / 100.0)


def _outcome(batch: Batch, model, discount: float, hour: float):
    price = batch.list_price * (1 - discount / 100.0)
    mean, lo, hi = model.expected_units(batch.category, batch.base_per_day, 1 - discount / 100.0, batch.days_left, hour)
    q = batch.qty
    ahead = batch.prior_qty
    sold, sold_lo, sold_hi = (min(q, max(0.0, v - ahead)) for v in (mean, lo, hi))
    net_price = net(price, batch.product_discount_pct)
    margin = sold * (net_price - batch.unit_cost)
    waste = max(0.0, q - sold) * batch.unit_cost
    value = sold * net_price - q * batch.unit_cost
    return price, net_price, sold, sold_lo, sold_hi, margin, waste, value


def choose(batch: Batch, policy: dict, model, hour: float = 6, ladder=LADDER) -> Decision:
    max_disc = float(policy.get("maxDiscountPct", 0))
    hard = float(policy.get("hardMarginFloorPct", 0))
    soft = float(policy.get("softMarginFloorPct", 0))
    list_net = net(batch.list_price, batch.product_discount_pct)
    base = _outcome(batch, model, 0, hour)
    best, blocked = (0, base), []
    for d in ladder:
        if d == 0:
            continue
        net_price = list_net * (1 - d / 100.0)
        if d > max_disc:
            blocked.append((d, "EXCEEDS_MAX_DISCOUNT"))
            continue
        if batch.unit_cost <= 0:
            blocked.append((d, "NO_COST"))
            continue
        if net_price < batch.unit_cost * (1 + hard / 100.0):
            blocked.append((d, "BELOW_HARD_FLOOR"))
            continue
        if net_price < batch.unit_cost * (1 + soft / 100.0):
            blocked.append((d, "BELOW_SOFT_FLOOR"))
            continue
        out = _outcome(batch, model, d, hour)
        if out[7] > best[1][7]:
            best = (d, out)
    d, out = best
    gain = out[7] - base[7]
    if d and gain < max(MIN_GAIN_PESOS, MIN_GAIN_SHARE * abs(base[7])):
        d, out, gain = 0, base, 0.0
    price, net_price, sold, sold_lo, sold_hi, margin, waste, value = out
    reason = ("no markdown: stock should sell before expiry" if d == 0 and base[6] <= 0.5 * batch.unit_cost
              else "no markdown helps enough" if d == 0 else
              f"{d:g}% off lifts expected sales from {base[2]:.1f} to {sold:.1f} units and cuts expected waste "
              f"from {base[6]:.0f} to {waste:.0f} pesos")
    return Decision(batch, d, round(price, 2), round(net_price, 2), sold, sold_lo, sold_hi, margin, waste,
                    base[2], base[6], gain, reason, blocked)

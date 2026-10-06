"""Price advisor: browse every product (with its COST) and suggest a selling price that maximises profit, within limits an
owner can trust. It SUGGESTS; nothing is applied here.

Demand is assumed to follow  units(p) = units_now * (p / p_now) ** beta  (beta < 0: a higher price sells less), with beta from
the learned demand model when the product's category has data, otherwise an assumed prior (reported as such).
Profit per day = (price - cost) * units. Guardrails on every suggestion:
  * a bounded step (default 10%) away from today's price, never a leap to the unconstrained optimum;
  * never below the owner's margin floor price (cost + hard floor);
  * a no-regret check: the suggestion must still be at least as profitable as today if customers turn out to be one full
    step MORE price-sensitive than assumed (beta - 1);
  * a product with no sales evidence gets no demand-based suggestion, only a margin check.
The margin price (the lowest price the rules allow) is reported for every product: it is the floor the markdown agent can use
later to clear short-dated stock."""
import math
from dataclasses import dataclass, asdict

DEFAULT_STEP_PCT = 10
COMPETITOR_CAP_PCT = 5.0          # never suggest a raise that lands more than this far above the lowest rival price
MIN_GAIN_PESOS_PER_DAY = 0.5
MIN_GAIN_SHARE = 0.02
STRESS_BETA_SHIFT = 1.0            # the no-regret scenario: customers this much more price-sensitive


@dataclass
class Suggestion:
    product_id: int
    name: str
    category: str
    cost: float
    price: float
    floor_price: float             # the margin price: lowest allowed price (cost + hard floor)
    soft_price: float              # below this a markdown needs approval (cost + soft floor)
    headroom_pct: float            # how far today's price can fall before it hits the margin price
    status: str                    # raise | lower | hold | no_evidence | margin_alert
    suggested_price: float
    change_pct: float
    units_per_day_now: float
    units_per_day_new: float
    profit_per_day_now: float
    profit_per_day_new: float
    profit_gain_per_day: float
    profit_gain_if_more_sensitive: float
    beta: float
    beta_source: str               # learned | assumed
    reason: str

    def to_dict(self):
        return asdict(self)


def _tick(price: float) -> float:
    return 0.5 if price < 50 else 1.0


def _round_to(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 2)


def floor_price(cost: float, hard_pct: float) -> float:
    t = _tick(cost)
    return round(math.ceil(cost * (1 + hard_pct / 100.0) / t - 1e-9) * t, 2)


def _profit(price: float, cost: float, units_now: float, price_now: float, beta: float) -> tuple:
    units = units_now * (price / price_now) ** beta
    return units, (price - cost) * units


def candidates(price: float, step_pct: int) -> list:
    t = _tick(price)
    out = {_round_to(price * (1 + k / 100.0), t) for k in range(-step_pct, step_pct + 1)}
    out.discard(_round_to(price, t))
    return sorted(p for p in out if p > 0)


def advise_one(p: dict, rate: float, beta: float, beta_source: str, policy: dict, step_pct: int = DEFAULT_STEP_PCT, competitor_low: float = None) -> Suggestion:
    """p: {id, name, category, cost, price}. rate: units per day at today's price (None or 0 = no evidence).
    competitor_low: the lowest price a rival charges for this product, if known; a raise is kept within COMPETITOR_CAP_PCT of it."""
    cost, price = float(p["cost"]), float(p["price"])
    hard, soft = float(policy.get("hardMarginFloorPct", 0)), float(policy.get("softMarginFloorPct", 0))
    fl = floor_price(cost, hard)
    sp = round(cost * (1 + soft / 100.0), 2)
    headroom = max(0.0, (price - fl) / price * 100.0) if price > 0 else 0.0

    def make(status, new_price, units_new, profit_new, gain_worst, reason, units_now=0.0, profit_now=0.0):
        return Suggestion(p["id"], p["name"], p["category"], cost, price, fl, sp, round(headroom, 1), status, new_price,
                          round((new_price - price) / price * 100.0, 1) if price else 0.0, round(units_now, 3), round(units_new, 3),
                          round(profit_now, 2), round(profit_new, 2), round(profit_new - profit_now, 2), round(gain_worst, 2), beta, beta_source, reason)

    if price < fl:
        return make("margin_alert", fl, 0.0, 0.0, 0.0, f"today's price {price:g} is below the margin price {fl:g} (cost {cost:g} + {hard:g}%); raise to at least {fl:g}")
    if not rate or rate <= 0:
        note = "no sales evidence yet, so no demand-based suggestion"
        if price < sp:
            note += f"; price sits inside the soft margin band (below {sp:g}), so it cannot be marked down without approval"
        return make("no_evidence", price, 0.0, 0.0, 0.0, note)
    units_now, profit_now = _profit(price, cost, rate, price, beta)
    best = (price, units_now, profit_now, 0.0)
    ceiling = competitor_low * (1 + COMPETITOR_CAP_PCT / 100.0) if competitor_low and competitor_low > 0 else None
    capped = False
    for cand in candidates(price, step_pct):
        if cand < fl:
            continue
        if ceiling is not None and cand > price and cand > ceiling:      # a raise above the rivals' reach is not suggested
            capped = True
            continue
        units, profit = _profit(cand, cost, rate, price, beta)
        _, worst_new = _profit(cand, cost, rate, price, beta - STRESS_BETA_SHIFT)
        _, worst_now = _profit(price, cost, rate, price, beta - STRESS_BETA_SHIFT)
        gain_worst = worst_new - worst_now
        if gain_worst < -MIN_GAIN_SHARE * abs(profit_now) - 1e-9:              # the no-regret check
            continue
        if profit > best[2]:
            best = (cand, units, profit, gain_worst)
    new_price, units_new, profit_new, gain_worst = best
    gain = profit_new - profit_now
    if new_price == price or gain < max(MIN_GAIN_PESOS_PER_DAY, MIN_GAIN_SHARE * abs(profit_now)):
        why = "today's price is already close to the best safe price" if gain <= 0 else "the possible gain is too small to act on"
        return make("hold", price, units_now, profit_now, 0.0, why, units_now, profit_now)
    direction = "raise" if new_price > price else "lower"
    src = "learned from this shop's sales" if beta_source == "learned" else "an assumed price sensitivity (not yet learned from sales)"
    reason = (f"{direction} {price:g} to {new_price:g} ({(new_price - price) / price * 100:+.0f}%): expected profit {profit_now:.1f} to {profit_new:.1f} pesos a day "
              f"with sensitivity {beta:.2f}, {src}; if customers are one step more price-sensitive the change still gains {gain_worst:.1f}")
    if capped and direction == "raise":
        reason += f"; held within {COMPETITOR_CAP_PCT:g}% of the lowest competitor price {competitor_low:g}"
    return make(direction, new_price, units_new, profit_new, gain_worst, reason, units_now, profit_now)


def advise(products: list, rates: dict, beta_for, policy: dict, step_pct: int = DEFAULT_STEP_PCT, competitor_low: dict = None) -> list:
    """products: dicts {id, name, category, cost, price}. rates: {product_id: units/day}. beta_for(category) -> (beta, source).
    competitor_low: {product_id: lowest rival price}, optional."""
    out = []
    for p in products:
        beta, src = beta_for(p["category"])
        out.append(advise_one(p, rates.get(p["id"]), beta, src, policy, step_pct, (competitor_low or {}).get(p["id"])))
    return out


def summarize(suggestions: list) -> dict:
    by = {}
    for s in suggestions:
        by[s.status] = by.get(s.status, 0) + 1
    acts = [s for s in suggestions if s.status in ("raise", "lower")]
    gain = sum(s.profit_gain_per_day for s in acts)
    conservative = sum(s.profit_gain_if_more_sensitive for s in acts)
    base = sum(s.profit_per_day_now for s in suggestions if s.units_per_day_now)
    return {"products": len(suggestions), "by_status": by, "expected_profit_gain_per_day": round(gain, 2),
            "conservative_gain_per_day": round(conservative, 2),
            "suggestions_on_assumed_sensitivity": sum(1 for s in acts if s.beta_source == "assumed"),
            "suggestions_on_learned_sensitivity": sum(1 for s in acts if s.beta_source == "learned"),
            "profit_per_day_now_on_products_with_evidence": round(base, 2),
            "products_below_margin_price": by.get("margin_alert", 0),
            "products_with_no_markdown_room": sum(1 for s in suggestions if s.price < s.soft_price)}

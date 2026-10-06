"""AI Replenish: what to reorder, how much, and when. It SUGGESTS; a person confirms and places the order.

For each product at a branch the question is: will the stock on hand last until a new delivery arrives? The delivery takes
`lead_days`. Sales are uncertain, so a safety allowance covers normal swings in demand (a service level of about 90 percent):

    reorder point = rate x lead + z x sigma x sqrt(lead)
    order up to   = rate x (lead + cover) + z x sigma x sqrt(lead)

If the stock on hand is at or below the reorder point, order enough to reach the order-up-to level, rounded up to a whole pack.
Perishable products are capped: never order more than will sell before the product expires (rate x shelf life). A product with no
sales evidence gets no suggestion. Everything here is arithmetic on the shop's own sales; nothing is learned from outside it."""
import math
import statistics
from dataclasses import asdict, dataclass

SERVICE_Z = 1.28            # about a 90 percent chance of not running out during the delivery wait
DEFAULT_LEAD_DAYS = 2
DEFAULT_COVER_DAYS = 7
MIN_DAYS_OF_DATA = 3        # fewer days of sales than this and no suggestion is made
LEARNED_DAYS = 7            # this many days or more is called "learned"; fewer is "limited"


@dataclass
class Suggestion:
    product_id: int
    name: str
    category: str
    on_hand: float
    rate_per_day: float
    days_of_cover: float
    reorder_point: float
    suggested_qty: float
    unit_cost: float
    lead_time_days: int
    cover_days: int
    confidence: str            # learned | limited
    urgent: bool               # the stock runs out before a new delivery could arrive
    reason: str

    def to_dict(self):
        return asdict(self)


def demand_from_daily(daily_units: list) -> tuple:
    """(rate per day, sigma per day, days of data) from one number per day, zero days included."""
    n = len(daily_units)
    if n == 0:
        return 0.0, 0.0, 0
    rate = sum(daily_units) / n
    sigma = statistics.pstdev(daily_units) if n > 1 else math.sqrt(rate)
    return rate, sigma, n


def demand_poisson(rate_per_day: float, days_of_data: int) -> tuple:
    """When only an average rate is known, treat sales as random arrivals: the spread of daily sales is then sqrt(rate)."""
    rate = max(0.0, float(rate_per_day))
    return rate, math.sqrt(rate), int(days_of_data)


def suggest(p: dict, rate: float, sigma: float, days_of_data: int, *, lead_days: int = DEFAULT_LEAD_DAYS, cover_days: int = DEFAULT_COVER_DAYS,
            service_z: float = SERVICE_Z, pack: int = 1, shelf_life_days: float = None, min_days_of_data: int = MIN_DAYS_OF_DATA):
    """p: {id, name, category, stock, cost}. Returns a Suggestion, or None when no order is needed or there is not enough evidence."""
    if rate <= 0 or days_of_data < min_days_of_data:
        return None
    on_hand = max(0.0, float(p.get("stock") or 0.0))
    safety = service_z * sigma * math.sqrt(lead_days)
    reorder_point = rate * lead_days + safety
    target = rate * (lead_days + cover_days) + safety
    capped = False
    if shelf_life_days:
        cap = rate * float(shelf_life_days)
        if cap < target:
            target, capped = cap, True
            reorder_point = min(reorder_point, target)
    if on_hand > reorder_point:
        return None
    need = target - on_hand
    if need <= 0:
        return None
    pack = max(1, int(pack))
    qty = math.ceil(need / pack) * pack
    cover = on_hand / rate
    urgent = cover <= lead_days
    why = (f"{on_hand:g} on hand covers {cover:.1f} days at about {rate:.1f} a day; a delivery takes {lead_days} days"
           + (", so it will run out first" if urgent else ", so order now to keep stock through the wait")
           + f". Order up to {target:.0f}" + (f" (limited to {shelf_life_days:g} days of sales because it expires)" if capped else "") + ".")
    return Suggestion(p["id"], p.get("name", ""), p.get("category", ""), round(on_hand, 2), round(rate, 3), round(cover, 1), round(reorder_point, 2),
                      float(qty), float(p.get("cost") or 0.0), int(lead_days), int(cover_days), "learned" if days_of_data >= LEARNED_DAYS else "limited", urgent, why)


def suggest_all(products: list, demand, **params) -> list:
    """demand(product) -> (rate, sigma, days_of_data) or None. Most urgent first (least cover left)."""
    out = []
    for p in products:
        d = demand(p)
        if d is None:
            continue
        s = suggest(p, *d, shelf_life_days=params.get("shelf_life_for", lambda _p: None)(p),
                    **{k: v for k, v in params.items() if k != "shelf_life_for"})
        if s:
            out.append(s)
    return sorted(out, key=lambda s: (not s.urgent, s.days_of_cover, -s.suggested_qty))

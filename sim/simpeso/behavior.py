"""Shoppers. Persistent named individuals come from archetypes; a day of visits is a deterministic function of the seed.

The hidden price response (archetype.price_response, the elasticity) is used ONLY here, to decide whether a shopper
puts an item in the basket at the price they actually see. The AI side never imports it and must estimate the
response from sales. The seed fixes the dice; it does not make people random: habits, home branch, missions and
wallet persist, and noise is small and bounded."""
from dataclasses import dataclass
from functools import lru_cache

from . import archetypes, rng
from .world import FIRST, LAST

REGULAR_SHARE = 0.65        # tunable design parameters, not measured facts
AVG_DAYS_BETWEEN_VISITS = 3
WALKIN_SHARE = 0.25
MAX_PRICE_BOOST = 3.0

HOUR_CURVES = {             # relative visit weight by hour (6..23) for each time pattern
    "morning":    {6: 3, 7: 6, 8: 6, 9: 3, 10: 1, 11: 1, 12: 1, 13: 1, 14: 0.5, 15: 0.5, 16: 0.5, 17: 0.5, 18: 0.5, 19: 0.3, 20: 0.2, 21: 0.1},
    "midday":     {9: 1, 10: 2, 11: 5, 12: 7, 13: 6, 14: 3, 15: 1, 16: 0.5, 17: 0.3},
    "evening":    {15: 0.5, 16: 1, 17: 4, 18: 7, 19: 7, 20: 4, 21: 2, 22: 1},
    "late_night": {20: 1, 21: 3, 22: 6, 23: 7},
    "weekend":    {8: 1, 9: 2, 10: 4, 11: 5, 12: 4, 13: 3, 14: 3, 15: 3, 16: 2, 17: 1},
}
MISSION_KEYWORDS = {
    "grab_and_go": ["meal", "bakery", "drink", "snack"],
    "after_work_topup": ["meal", "drink", "snack", "dairy", "personal"],
    "late_night": ["meal", "snack", "drink"],
    "weekly_restock": ["produce", "dairy", "meat", "canned", "household", "drink", "snack"],
    "urgent_medicine": ["medicine"],
    "repair_urgent": ["brake", "drive", "electrical", "tire", "hardware", "oil"],
    "scheduled_maintenance": ["oil", "brake", "drive", "tire"],
    "accessory_browse": ["accessor"],
    "event_driven": ["ball", "apparel", "footwear"],
    "hobby": ["equipment", "ball", "apparel"],
}


@dataclass(frozen=True)
class Individual:
    id: str
    name: str
    archetype: str
    company: str
    home_branch: str
    wallet: int
    visits_per_week: float
    weekend_shopper: bool


@dataclass(frozen=True)
class Visit:
    id: str
    day: int
    hour: int
    minute: int
    company: str
    branch: str
    shopper: str
    archetype: str
    mission: str
    lines: tuple            # ((product_code, quantity), ...)
    payment: str


def _branches(plan):
    for c in plan.companies:
        for b in c.branches:
            yield c, b


def pool_size(plan, branch) -> int:
    s = plan.settings
    raw = branch.txns_per_day * s["traffic_scale"] * REGULAR_SHARE * AVG_DAYS_BETWEEN_VISITS
    return max(8, round(raw)) if s["regular_pool"] is None else max(8, min(round(raw), s["regular_pool"] * 4))


def make_individuals(plan, seed: int) -> list:
    lib = list(_library().values())
    people = []
    for c, b in _branches(plan):
        fit = [a for a in lib if b.vertical in a.verticals]
        weights = [a.visits_per_week for a in fit]
        r = rng.derive(seed, "individuals", b.key)
        for n in range(pool_size(plan, b)):
            a = r.choices(fit, weights=weights)[0]
            wallet = round({"low": 150, "mid": 400, "high": 1200}[a.income] * r.uniform(0.7, 1.4))
            people.append(Individual(f"{b.key}-i{n + 1:04d}", f"{r.choice(FIRST)} {r.choice(LAST)}", a.id, c.key, b.key,
                                     wallet, round(a.visits_per_week * r.uniform(0.8, 1.2), 2), a.time == "weekend"))
    return people


def _is_weekend(day: int) -> bool:
    return day % 7 in (5, 6)


def _hour_weights(time_pattern: str) -> tuple:
    curve = HOUR_CURVES[time_pattern]
    return tuple(curve), tuple(curve.values())


@lru_cache(maxsize=None)
def _popularity(seed: int, code: str) -> float:
    return 0.5 + rng.derive(seed, "popularity", code).random()


@lru_cache(maxsize=None)
def _product_weights(catalog: tuple, mission: str, seed: int) -> tuple:
    words = MISSION_KEYWORDS.get(mission, [])
    return tuple(_popularity(seed, p.code) * p.popularity * (3.0 if any(w in p.category.lower() for w in words) else 0.3) for p in catalog)


@lru_cache(maxsize=None)
def _library() -> dict:
    return {a.id: a for a in archetypes.customer_archetypes()}


def _buy_probability(base: float, elasticity: float, ratio: float, noise: float) -> float:
    boost = min(MAX_PRICE_BOOST, max(0.05, ratio) ** (-elasticity))
    return max(0.0, min(0.98, base * boost * noise))


def day_arrivals(plan, individuals: list, day: int, seed: int, calib=None) -> list:
    """Who walks in, where and when, with their mission. Baskets are decided later, at the moment of shopping,
    so shoppers see the prices in force at that hour (see fill_basket)."""
    lib = _library()
    by_branch = {}
    for p in individuals:
        by_branch.setdefault(p.home_branch, []).append(p)
    out = []
    for c, b in _branches(plan):
        if day < b.opens_day:
            continue
        r = rng.derive(seed, "day", day, b.key)
        pool = by_branch.get(b.key, [])
        weekend = _is_weekend(day)
        todays = []
        for ind in pool:
            a = lib[ind.archetype]
            p = ind.visits_per_week / 7.0
            if ind.weekend_shopper:
                p *= 3.0 if weekend else 0.25
            elif weekend:
                p *= 0.85
            if r.random() < min(0.95, p * AVG_DAYS_BETWEEN_VISITS / 3.0):
                todays.append((ind.id, a))
        walkins = round(len(todays) * WALKIN_SHARE)
        fit = [a for a in lib.values() if b.vertical in a.verticals]
        for n in range(walkins):
            todays.append((f"walkin-{day}-{b.key}-{n + 1}", r.choices(fit, weights=[a.visits_per_week for a in fit])[0]))
        for n, (who, a) in enumerate(todays):
            hours, hw = _hour_weights(a.time)
            if calib is not None:                      # blend with the real hour-of-day profile (see calibration.py)
                curve = HOUR_CURVES[a.time]
                base = [curve.get(h, 0.0) for h in range(OPEN_H, CLOSE_H)]
                tot = sum(base) or 1.0
                hours, hw = tuple(range(OPEN_H, CLOSE_H)), tuple(calib.blend([x / tot for x in base]))
            hour = r.choices(hours, weights=hw)[0]
            if day == b.opens_day and hour < b.opens_hour:
                continue
            valid = [(m, w) for m, w in a.missions.items() if m in _vertical_missions(b.vertical)]
            if not valid:
                continue
            mission = r.choices([m for m, _ in valid], weights=[w for _, w in valid])[0]
            pay = "Card" if (a.income == "high" and r.random() < 0.6) or r.random() < 0.1 else "Cash"
            out.append(Visit(f"d{day}-{b.key}-v{n + 1}", day, hour, r.randint(0, 59), c.key, b.key, who, a.id, mission, (), pay))
    out.sort(key=lambda v: (v.hour, v.minute, v.id))
    return out


def fill_basket(plan, visit: Visit, seed: int, price_ratio=None, calib=None):
    """The shopper's basket at the prices in force now. price_ratio(branch, product_code) -> current/list price.
    Returns the visit with lines, or None when they buy nothing."""
    from dataclasses import replace
    ratio = price_ratio or (lambda branch, code: 1.0)
    a = _library()[visit.archetype]
    catalog = tuple(next(c for c in plan.companies if c.key == visit.company).catalog)
    r = rng.derive(seed, "basket", visit.id)
    weights = _product_weights(catalog, visit.mission, seed)
    wanted = max(1, round(a.basket * (calib.basket_scale if calib is not None else 1.0) * r.uniform(0.6, 1.4)))
    chosen = {}
    for _ in range(wanted * 3):
        if len(chosen) >= wanted:
            break
        prod = r.choices(catalog, weights=weights)[0]
        ratio_now = ratio(visit.branch, prod.code)
        q = _buy_probability(0.6, a.price_response, ratio_now, r.uniform(0.9, 1.1))
        if r.random() < q:
            qty = 1 + (1 if r.random() < max(0.0, (ratio_now < 1.0) * 0.25 * a.price_response) else 0)
            chosen[prod.code] = chosen.get(prod.code, 0) + qty
    if not chosen:
        return None
    return replace(visit, lines=tuple(sorted(chosen.items())))


def respond_to_prices(visit: Visit, lines, seed: int, price_ratio=None):
    """A basket someone else chose (a real data set), put through this shopper's reaction to the prices in force now. A line the shopper would
    skip at today's price is dropped; a cheaper price can add a unit. At list price almost every line stays. Returns the visit with lines, or None.
    The hidden price response is read here and nowhere else."""
    from dataclasses import replace
    ratio = price_ratio or (lambda branch, code: 1.0)
    a = _library()[visit.archetype]
    r = rng.derive(seed, "replay-response", visit.id)
    kept = {}
    for code, qty in lines:
        ratio_now = ratio(visit.branch, code)
        if r.random() < _buy_probability(1.0, a.price_response, ratio_now, r.uniform(0.95, 1.05)):
            extra = 1 if r.random() < max(0.0, (ratio_now < 1.0) * 0.25 * a.price_response) else 0
            kept[code] = kept.get(code, 0) + qty + extra
    return replace(visit, lines=tuple(sorted(kept.items()))) if kept else None


def day_visits(plan, individuals: list, day: int, seed: int, price_ratio=None, calib=None) -> list:
    """All visits of one virtual day with baskets, sorted by time (prices fixed for the whole day)."""
    filled = (fill_basket(plan, v, seed, price_ratio, calib) for v in day_arrivals(plan, individuals, day, seed, calib))
    return [v for v in filled if v]


@lru_cache(maxsize=None)
def _vertical_missions(vertical: str) -> tuple:
    from . import verticals
    return verticals.load_all()[vertical].missions


def population_arrays() -> dict:
    """Per-archetype arrays for the vectorised Quick Sim lane (numpy). The hidden price response is returned here, inside
    behavior.py, so the aggregated lane can simulate shoppers without any other module naming it."""
    import numpy as np
    lib = list(_library().values())
    hours = list(range(OPEN_H, CLOSE_H))
    hour_weights = np.array([[HOUR_CURVES[a.time].get(h, 0.0) for h in hours] for a in lib], dtype=np.float64)
    hour_weights /= hour_weights.sum(axis=1, keepdims=True)
    return {"ids": [a.id for a in lib], "hours": hours, "hour_weights": hour_weights,
            "visits_per_week": np.array([a.visits_per_week for a in lib]), "basket": np.array([a.basket for a in lib], dtype=np.float64),
            "weekend_shopper": np.array([a.time == "weekend" for a in lib]), "response": np.array([a.price_response for a in lib])}


OPEN_H, CLOSE_H = 6, 24

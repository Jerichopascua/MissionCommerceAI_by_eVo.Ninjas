"""Seeing customers change their behavior. The shop's own purchase records (day, hour, price paid, list price, quantity)
are enough to ask: did people start buying later, did more units move at the clearance price, did full-price sales fall?
Nothing here knows who the customers are or why they changed; it only measures the change and tests whether it is
bigger than chance (a seeded permutation test on the mean purchase hour)."""
import random

DISCOUNT_BELOW = 0.95        # a sale below 95% of list price counts as a clearance sale


def _hours(events):
    return [e["hour"] for e in events for _ in range(int(e["qty"]))]


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if n == 0 else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def _period(events, days):
    ev = [e for e in events if e["day"] in days]
    units = sum(e["qty"] for e in ev)
    disc = sum(e["qty"] for e in ev if e["price"] < DISCOUNT_BELOW * e["list_price"])
    full = units - disc
    n = max(1, len(days))
    hours = _hours(ev)
    return {"days": len(days), "units_per_day": units / n, "full_price_units_per_day": full / n,
            "discount_units_per_day": disc / n, "discount_share": (disc / units) if units else 0.0,
            "median_hour": _median(hours), "mean_hour": (sum(hours) / len(hours)) if hours else None,
            "revenue_per_day": sum(e["price"] * e["qty"] for e in ev) / n}


def _perm_p(a, b, seed, n_perm):
    if not a or not b:
        return 1.0
    rnd = random.Random(seed)
    obs = abs(sum(a) / len(a) - sum(b) / len(b))
    pooled, na, hits = a + b, len(a), 0
    for _ in range(n_perm):
        rnd.shuffle(pooled)
        if abs(sum(pooled[:na]) / na - sum(pooled[na:]) / len(b)) >= obs:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def detect_shift(events: list, before_days, after_days, seed: int = 0, n_perm: int = 2000,
                 min_shift_hours: float = 0.5, alpha: float = 0.01) -> dict:
    """events: dicts with day, hour, price, list_price, qty. Compares two sets of days."""
    before, after = _period(events, set(before_days)), _period(events, set(after_days))
    hb, ha = _hours([e for e in events if e["day"] in set(before_days)]), _hours([e for e in events if e["day"] in set(after_days)])
    shift = None if before["mean_hour"] is None or after["mean_hour"] is None else after["mean_hour"] - before["mean_hour"]
    p = _perm_p(hb, ha, seed, n_perm)
    shifted = shift is not None and abs(shift) >= min_shift_hours and p < alpha
    return {"before": before, "after": after, "mean_hour_shift": shift, "p_value": p, "shifted": shifted,
            "full_price_change_per_day": after["full_price_units_per_day"] - before["full_price_units_per_day"],
            "discount_share_change": after["discount_share"] - before["discount_share"],
            "verdict": verdict(before, after, shift, shifted)}


def _clock(h):
    return "-" if h is None else f"{int(h):02d}:{int(round((h - int(h)) * 60)):02d}"


def verdict(before, after, shift, shifted) -> str:
    if not shifted:
        return "No reliable change in when customers buy."
    direction = "later" if shift > 0 else "earlier"
    return (f"Customers now buy {abs(shift):.1f} h {direction} (median {_clock(before['median_hour'])} -> {_clock(after['median_hour'])}); "
            f"clearance-priced units went from {before['discount_share'] * 100:.0f}% to {after['discount_share'] * 100:.0f}% of sales, "
            f"and full-price units from {before['full_price_units_per_day']:.1f} to {after['full_price_units_per_day']:.1f} per day.")

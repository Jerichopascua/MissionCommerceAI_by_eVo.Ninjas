"""Learning price sensitivity from a controlled price test.

Design: some shops (treatment) raise the price of a set of products for a few days while comparable shops (control) keep
theirs. For each product we compare how treatment sales changed against how control sales changed over the same days
(difference in differences), which removes the common day-to-day swings and the fact that shops differ in size:

    d_p = ln( (treat_test/treat_base) / (control_test/control_base) ),   x_p = ln(new price / old price)

Under  units ~ price ** beta  we have  d_p = beta * x_p,  so beta is a weighted least-squares slope through the origin, with
Poisson variance weights. The result carries a standard error and a 95% interval; with few units the interval is wide, and
the report says so instead of pretending."""
import math
from dataclasses import dataclass


@dataclass
class ProductResult:
    product_id: int
    x: float                    # ln(price ratio)
    d: float                    # difference-in-differences of log sales rate
    weight: float
    treat_base: float
    treat_test: float
    control_base: float
    control_test: float


def did_estimate(rows: list, days_base: float, days_test: float) -> dict:
    """rows: dicts {product_id, x, treat_base, treat_test, control_base, control_test} (unit totals over each phase)."""
    results, num, den = [], 0.0, 0.0
    for r in rows:
        x = float(r["x"])
        if abs(x) < 1e-9:
            continue
        tb, tt, cb, ct = (float(r[k]) + 0.5 for k in ("treat_base", "treat_test", "control_base", "control_test"))   # +0.5 keeps zeros usable
        d = math.log((tt / days_test) / (tb / days_base)) - math.log((ct / days_test) / (cb / days_base))
        var = 1 / tt + 1 / tb + 1 / ct + 1 / cb
        w = 1.0 / var
        results.append(ProductResult(r["product_id"], x, d, w, tb - 0.5, tt - 0.5, cb - 0.5, ct - 0.5))
        num += w * x * d
        den += w * x * x
    if den <= 0:
        return {"beta": None, "se": None, "ci95": None, "products": 0, "treated_units_test": 0, "control_units_test": 0, "reliable": False}
    beta, se = num / den, 1.0 / math.sqrt(den)
    ci = [beta - 1.96 * se, beta + 1.96 * se]
    return {"beta": beta, "se": se, "ci95": ci, "products": len(results),
            "treated_units_test": sum(r.treat_test for r in results), "control_units_test": sum(r.control_test for r in results),
            "reliable": se < 0.75, "per_product": [r.__dict__ for r in results]}


def as_observations(rows: list, days_base: float, days_test: float) -> list:
    """Turn the test into model observations (log price ratio, expected units without the change, observed units) for each
    treated product, where 'expected without the change' is the treatment base rate scaled by the control trend."""
    out = []
    for r in rows:
        x = float(r["x"])
        if abs(x) < 1e-9:
            continue
        tb, cb, ct = (float(r[k]) + 0.5 for k in ("treat_base", "control_base", "control_test"))
        trend = (ct / days_test) / (cb / days_base)
        expected = (tb / days_base) * trend * days_test
        out.append({"x": x, "expected_units": expected, "units": float(r["treat_test"]), "product_id": r["product_id"]})
    return out


def switchback_estimate(rows: list, days_raised: float, days_normal: float) -> dict:
    """Every shop alternates between the raised and the normal price on randomized days, so each shop is its own control.
    rows: dicts {product_id, x, raised_units, normal_units} (unit totals over all shops, over the raised and the normal days).
    d_p = ln((raised/days_raised) / (normal/days_normal)), beta = weighted slope of d on x through the origin, Poisson weights."""
    results, num, den = [], 0.0, 0.0
    for r in rows:
        x = float(r["x"])
        if abs(x) < 1e-9:
            continue
        ur, un = float(r["raised_units"]) + 0.5, float(r["normal_units"]) + 0.5
        d = math.log((ur / days_raised) / (un / days_normal))
        w = 1.0 / (1 / ur + 1 / un)
        results.append({"product_id": r["product_id"], "x": x, "d": d, "weight": w, "raised_units": ur - 0.5, "normal_units": un - 0.5})
        num += w * x * d
        den += w * x * x
    if den <= 0:
        return {"beta": None, "se": None, "ci95": None, "products": 0, "raised_units": 0, "normal_units": 0, "reliable": False}
    beta, se = num / den, 1.0 / math.sqrt(den)
    return {"beta": beta, "se": se, "ci95": [beta - 1.96 * se, beta + 1.96 * se], "products": len(results),
            "raised_units": sum(r["raised_units"] for r in results), "normal_units": sum(r["normal_units"] for r in results),
            "reliable": se < 0.75, "per_product": results}


def randomized_days(n_days: int, seed: int) -> list:
    """Balanced assignment: within each consecutive pair of days one is raised and one is normal, in random order, so weekday
    effects cancel. Returns a list of booleans (True = raised price that day)."""
    import random
    rnd = random.Random(seed)
    out = []
    for _ in range(n_days // 2):
        pair = [True, False]
        rnd.shuffle(pair)
        out += pair
    if n_days % 2:
        out.append(rnd.random() < 0.5)
    return out

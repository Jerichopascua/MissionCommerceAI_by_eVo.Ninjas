"""AI Customer Mission: what were shoppers trying to get done in a visit?

It reads purchases only: when the basket was bought, how many different products, how many units, how much it came to, and whether
it held anything perishable. It cannot see intent, so a mission here is an inference from the shape of the basket, and the rules are
plain enough to read and challenge. Each basket gets one mission, the first rule that matches:

    Weekly restock        a big basket: 8 or more lines, or 12 or more units, or three times the usual basket value
    Late night            bought between 22:00 and 05:00
    Morning grab-and-go   5:00 to 10:00 and no more than 3 lines
    Dinner run            16:00 to 22:00 with something perishable in it
    After-work top-up     16:00 to 22:00, 2 to 6 lines
    Quick top-up          1 or 2 lines at any other time
    Everyday shop         anything else

The summary says, per branch, how many baskets, what share each mission is, the typical basket and the busiest hour, with a sentence
on what that means for stock and staffing. Nothing here is learned from outside the shop; it is arithmetic on its own sales."""
import statistics
from collections import Counter
from dataclasses import dataclass

WEEKLY_RESTOCK = "Weekly restock"
LATE_NIGHT = "Late night"
MORNING = "Morning grab-and-go"
DINNER = "Dinner run"
AFTER_WORK = "After-work top-up"
QUICK = "Quick top-up"
EVERYDAY = "Everyday shop"
MISSIONS = (WEEKLY_RESTOCK, LATE_NIGHT, MORNING, DINNER, AFTER_WORK, QUICK, EVERYDAY)

RESTOCK_LINES = 8
RESTOCK_UNITS = 12.0
RESTOCK_VALUE_MULTIPLE = 3.0
MIN_BASKETS = 10            # fewer baskets than this and no summary is made for the mission


@dataclass
class Basket:
    hour: int
    lines: int
    units: float
    value: float
    perishable: bool = False


def classify(b: Basket, median_value: float = 0.0) -> str:
    h = b.hour
    if b.lines >= RESTOCK_LINES or b.units >= RESTOCK_UNITS or (median_value > 0 and b.value >= RESTOCK_VALUE_MULTIPLE * median_value and b.lines >= 3):
        return WEEKLY_RESTOCK
    if h >= 22 or h < 5:
        return LATE_NIGHT
    if 5 <= h < 10 and b.lines <= 3:
        return MORNING
    if 16 <= h < 22 and b.perishable:
        return DINNER
    if 16 <= h < 22 and 2 <= b.lines <= 6:
        return AFTER_WORK
    if b.lines <= 2:
        return QUICK
    return EVERYDAY


ADVICE = {
    WEEKLY_RESTOCK: "Big baskets: keep staples (rice, oil, detergent, drinks) in deep stock before the busy days and add a second checkout lane when it is busy.",
    LATE_NIGHT: "Late shoppers buy a few things: keep water, snacks, medicine and cigarettes-free essentials stocked and the till open.",
    MORNING: "Morning visits are quick: have bread, coffee and drinks ready and the front shelves filled before opening.",
    DINNER: "Shoppers are buying fresh food for dinner: stock the fresh counter by late afternoon, and mark down what is left after the evening peak.",
    AFTER_WORK: "After-work shoppers pick up a few items on the way home: keep ready-to-eat items and drinks at the front and the checkout fast.",
    QUICK: "Most visits are one or two items: keep the checkout fast and put impulse items near the till.",
    EVERYDAY: "Mixed everyday shopping: keep the full range visible and stocked.",
}


def insight(mission: str, share_pct: float, peak_hour, avg_items: float, avg_value: float) -> str:
    when = f", busiest around {peak_hour:02d}:00" if peak_hour is not None else ""
    return f"{mission} is {share_pct:.0f}% of baskets{when}; a typical one has {avg_items:.1f} items and comes to ₱{avg_value:,.0f}. {ADVICE.get(mission, '')}"


def summarize(baskets: list, window_days: int = 14, min_baskets: int = MIN_BASKETS) -> list:
    """Per-mission rows for one branch: {mission, baskets, share_pct, avg_items, avg_value, peak_hour, insight, window_days}, biggest share first."""
    if len(baskets) < min_baskets:
        return []
    median_value = statistics.median(b.value for b in baskets)
    by = {}
    for b in baskets:
        by.setdefault(classify(b, median_value), []).append(b)
    total = len(baskets)
    rows = []
    for mission, group in by.items():
        share = len(group) / total * 100.0
        hours = Counter(b.hour for b in group)
        peak = max(hours, key=lambda h: (hours[h], -h)) if hours else None
        avg_items = sum(b.lines for b in group) / len(group)
        avg_value = sum(b.value for b in group) / len(group)
        rows.append({"mission": mission, "baskets": len(group), "share_pct": round(share, 2), "avg_items": round(avg_items, 2), "avg_value": round(avg_value, 2),
                     "peak_hour": peak, "insight": insight(mission, share, peak, avg_items, avg_value), "window_days": window_days})
    return sorted(rows, key=lambda r: -r["baskets"])


# What the simulator's shoppers were really doing, matched to the missions above, for scoring the classifier. A prediction counts as right
# if it is one of the missions that truth could reasonably look like in a basket. (Used only in tests and the scoring script.)
ACCEPTED = {
    "weekly_restock": {WEEKLY_RESTOCK},
    "late_night": {LATE_NIGHT},
    "after_work_topup": {AFTER_WORK, DINNER},
    "grab_and_go": {QUICK, MORNING},
    "urgent_medicine": {QUICK, MORNING, LATE_NIGHT},
    "hobby": {QUICK, EVERYDAY},
}


def score(pairs: list) -> dict:
    """pairs: [(true mission id, predicted mission)]. Returns overall and per-true-mission agreement."""
    per = {}
    for truth, pred in pairs:
        ok = pred in ACCEPTED.get(truth, {pred})
        t = per.setdefault(truth, [0, 0])
        t[0] += 1
        t[1] += 1 if ok else 0
    n = sum(v[0] for v in per.values())
    hit = sum(v[1] for v in per.values())
    return {"baskets": n, "agreement": round(hit / n, 3) if n else None,
            "by_truth": {k: {"baskets": v[0], "agreement": round(v[1] / v[0], 3)} for k, v in sorted(per.items())}}

"""Which products in a real catalog are perishable, and for how long. The real source data has NO expiry information, so this
is an explicit, reviewable rule list on product names (a design choice, not a measured fact). Shelf-life ranges follow the
design's category profiles: chilled dairy 7 to 21 days, chilled meat 14 to 45, prepared salad 3 to 7, and so on.

Everything not matched stays non-expiry (soap, instant noodles, canned goods, wafers, cleaning products...). Each rule is
anchored on specific words so that e.g. 'SAMYANG BULDAK CHEESE' (instant noodles) or 'SURF ROSE FRESH' (detergent) never match."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    category: str
    pattern: re.Pattern
    shelf_life_days: tuple
    popularity_floor: float      # chilled staples sell daily in a real store even when our small real sample saw none


def _r(category, pattern, shelf, pop):
    return Rule(category, re.compile(pattern, re.I), shelf, pop)


RULES = (
    _r("Chilled dairy", r"\bYAKULT\b|\bFRESH MILK\b", (7, 21), 2.0),
    _r("Chilled dairy", r"\bSOYMILK\b", (30, 90), 1.0),
    _r("Chilled spreads and cheese", r"\bMARGARINE\b|\bPARMESAN\b", (60, 120), 0.6),
    _r("Chilled meat", r"\bVIDA (SWEET )?HAM\b|\bVIDA BACON\b|\bCHICKEN DRUMMETS\b|\bCRAZY CUT NUGGETS\b|\bCHICKEN TAPA\b|\bBEEF TAPA\b|\bSISIG\b", (14, 45), 0.8),
    _r("Prepared salad", r"\bSALAD MACARONI\b", (3, 7), 1.5),
    _r("Chilled side dishes", r"\bKIMCHI\b", (21, 45), 0.6),
    _r("Packaged cakes", r"\bWHOOPIE\b|\bDONUT\b", (45, 90), 0.6),
)


def classify(name: str):
    for rule in RULES:
        if rule.pattern.search(name):
            return rule
    return None


def alert_days(shelf_life_days: tuple) -> int:
    """Start watching a batch when about a third of the minimum shelf life is left, at least 2 and at most 30 days."""
    return max(2, min(30, round(shelf_life_days[0] / 3)))

"""Vertical templates are data (YAML), not code. A template defines catalog size, categories with shelf-life
profiles, a margin band, ticket size, expiry on/off, shopper missions and a traffic band."""
from dataclasses import dataclass
from pathlib import Path
import math
import yaml

DATA_DIR = Path(__file__).parent / "data" / "verticals"
REQUIRED = ("name", "tier", "expiry", "catalog_size", "margin_band", "ticket", "txns_per_day", "missions", "categories")


@dataclass(frozen=True)
class Category:
    name: str
    expiry: bool
    shelf_life_days: tuple
    weight: int
    cost: tuple
    items: tuple


@dataclass(frozen=True)
class Vertical:
    name: str
    tier: str
    expiry: bool
    catalog_size: tuple
    margin_band: tuple
    ticket: tuple
    txns_per_day: tuple
    missions: tuple
    categories: tuple


@dataclass(frozen=True)
class ProductSpec:
    code: str
    name: str
    category: str
    cost: int
    price: int
    expiry: bool
    shelf_life_days: tuple = ()
    alert_days: int = 0
    popularity: float = 1.0          # relative pull on shoppers; real sales concentration for a real catalog


def _from_dict(d: dict) -> Vertical:
    cats = tuple(Category(c["name"], bool(c.get("expiry", False)), tuple(c.get("shelf_life_days") or ()),
                          int(c.get("weight", 1)), tuple(c["cost"]), tuple(c["items"])) for c in d.get("categories", []))
    return Vertical(d["name"], d["tier"], bool(d["expiry"]), tuple(d["catalog_size"]), tuple(d["margin_band"]),
                    tuple(d["ticket"]), tuple(d["txns_per_day"]), tuple(d["missions"]), cats)


def load_all() -> dict:
    out = {}
    for path in sorted(DATA_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        problems = validate_raw(raw)
        if problems:
            raise ValueError(f"{path.name}: " + "; ".join(problems))
        out[raw["name"]] = _from_dict(raw)
    return out


def validate_raw(raw: dict) -> list:
    problems = []
    for key in REQUIRED:
        if key not in raw:
            problems.append(f"missing {key}")
    if problems:
        return problems
    lo, hi = raw["margin_band"]
    if not (0 < lo < hi < 0.9):
        problems.append(f"margin band {raw['margin_band']} is not a sane (low, high) pair")
    if raw["catalog_size"][0] > raw["catalog_size"][1]:
        problems.append("catalog_size range is reversed")
    if not raw["categories"]:
        problems.append("no categories")
    if not raw["missions"]:
        problems.append("no missions")
    for c in raw["categories"]:
        if not c.get("items"):
            problems.append(f"category {c.get('name')} has no items")
        if c.get("expiry") and not c.get("shelf_life_days"):
            problems.append(f"expiry category {c.get('name')} has no shelf_life_days")
        if c.get("expiry") and not raw["expiry"]:
            problems.append(f"category {c.get('name')} expires but the vertical says expiry is off")
        if c["cost"][0] > c["cost"][1]:
            problems.append(f"category {c.get('name')} cost range is reversed")
    return problems


def validate(v: Vertical) -> list:
    raw = {"name": v.name, "tier": v.tier, "expiry": v.expiry, "catalog_size": list(v.catalog_size),
           "margin_band": list(v.margin_band), "ticket": list(v.ticket), "txns_per_day": list(v.txns_per_day),
           "missions": list(v.missions),
           "categories": [{"name": c.name, "expiry": c.expiry, "shelf_life_days": list(c.shelf_life_days),
                           "cost": list(c.cost), "items": list(c.items)} for c in v.categories]}
    return validate_raw(raw)


def margin_of(cost: int, price: int) -> float:
    return (price - cost) / price


def build_catalog(v: Vertical, rnd, size: int) -> list:
    lo, hi = v.margin_band
    size = max(1, min(size, v.catalog_size[1]))
    weights = [c.weight for c in v.categories]
    counters = {c.name: 0 for c in v.categories}
    specs = []
    for i in range(size):
        cat = rnd.choices(v.categories, weights=weights)[0]
        n = counters[cat.name]
        counters[cat.name] += 1
        base = cat.items[n % len(cat.items)]
        variant = n // len(cat.items)
        name = base if variant == 0 else f"{base} {chr(ord('A') + variant)}"
        cost = rnd.randint(int(cat.cost[0]), int(cat.cost[1]))
        target = rnd.uniform(lo, hi)
        price = max(cost + 1, round(cost / (1 - target)))
        while margin_of(cost, price) > hi and price > cost + 1:
            price -= 1
        while margin_of(cost, price) < lo:
            price += 1
        alert = 0
        if cat.expiry:
            alert = max(1, min(30, math.ceil(sum(cat.shelf_life_days) / 2 * 0.5)))
        specs.append(ProductSpec(f"{v.name[:3].upper()}-{i + 1:04d}", name, cat.name, cost, price,
                                 cat.expiry, tuple(cat.shelf_life_days), alert))
    return specs

"""Customer and owner archetype libraries (data in YAML) with the validators that keep them honest:
the coverage grid must have no empty cell and no two archetypes may read as near-duplicates."""
from dataclasses import dataclass
from pathlib import Path
import re
import yaml

from . import verticals as vt

DATA_DIR = Path(__file__).parent / "data"
AGES = ("young", "adult", "senior")
INCOMES = ("low", "mid", "high")
TIMES = ("morning", "midday", "evening", "late_night", "weekend")
MOBILITY = ("walker", "rider", "car", "commuter")
SIMILARITY_LIMIT = 0.8


@dataclass(frozen=True)
class CustomerArchetype:
    id: str
    text: str
    age: str
    income: str
    household: str
    mobility: str
    time: str
    verticals: tuple
    missions: dict
    price_response: float   # hidden elasticity; only behavior.py may read it
    visits_per_week: float
    basket: int


@dataclass(frozen=True)
class OwnerArchetype:
    id: str
    text: str
    capital: str
    ambition: int
    risk: str
    expansion_chance: float
    verticals: tuple
    staff_per_branch: tuple
    catalog_share: float
    conglomerate: bool


def customer_archetypes() -> list:
    raw = yaml.safe_load((DATA_DIR / "customer_archetypes.yaml").read_text(encoding="utf-8"))
    return [CustomerArchetype(r["id"], r["text"], r["age"], r["income"], r["household"], r["mobility"], r["time"],
                              tuple(r["verticals"]), dict(r["missions"]), float(r["price_response"]),
                              float(r["visits_per_week"]), int(r["basket"])) for r in raw]


def owner_archetypes() -> list:
    raw = yaml.safe_load((DATA_DIR / "owner_archetypes.yaml").read_text(encoding="utf-8"))
    return [OwnerArchetype(r["id"], r["text"], r["capital"], int(r["ambition"]), r["risk"], float(r["expansion_chance"]),
                           tuple(r["verticals"]), tuple(r["staff_per_branch"]), float(r["catalog_share"]),
                           bool(r["conglomerate"])) for r in raw]


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def validate_library(lib: list, verts: dict = None, min_per_vertical: int = 6) -> list:
    verts = verts or vt.load_all()
    problems = []
    ids = [a.id for a in lib]
    if len(ids) != len(set(ids)):
        problems.append("duplicate archetype ids")
    covered_it = {(a.income, a.time) for a in lib}
    for inc in INCOMES:
        for t in TIMES:
            if (inc, t) not in covered_it:
                problems.append(f"empty grid cell: income={inc} time={t}")
    covered_ai = {(a.age, a.income) for a in lib}
    for age in AGES:
        for inc in INCOMES:
            if (age, inc) not in covered_ai:
                problems.append(f"empty grid cell: age={age} income={inc}")
    for m in MOBILITY:
        if not any(a.mobility == m for a in lib):
            problems.append(f"no archetype with mobility={m}")
    for a in lib:
        if abs(sum(a.missions.values()) - 1.0) > 0.01:
            problems.append(f"{a.id}: mission weights do not sum to 1")
        if a.price_response <= 0:
            problems.append(f"{a.id}: price_response must be positive")
        for v in a.verticals:
            if v not in verts:
                problems.append(f"{a.id}: unknown vertical {v}")
            elif not any(m in verts[v].missions for m in a.missions):
                problems.append(f"{a.id}: no mission that fits vertical {v}")
    for name, v in verts.items():
        n = sum(1 for a in lib if name in a.verticals)
        if n < min_per_vertical:
            problems.append(f"vertical {name} has only {n} archetypes (need {min_per_vertical})")
    for i, a in enumerate(lib):
        for b in lib[i + 1:]:
            if similarity(a.text, b.text) >= SIMILARITY_LIMIT:
                problems.append(f"near-duplicate archetypes: {a.id} and {b.id}")
    return problems

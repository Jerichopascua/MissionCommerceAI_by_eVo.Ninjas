"""Incident injection plan and the ground-truth ledger. The simulator injects an incident, records it here, and
scoring later checks who noticed. Wording is always "unexplained", never an accusation: staff keys appear in the
ledger as plain identifiers only."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import rng

CASH_SHORT = "CASH_SHORT"
NEAR_EXPIRY_BATCH = "NEAR_EXPIRY_BATCH"
UNREPORTED_SHORT_DELIVERY = "UNREPORTED_SHORT_DELIVERY"
HIDDEN_SHRINK = "HIDDEN_SHRINK"

# The PesoWeb Exception Center rule that should raise each incident. None = PesoWeb has no rule for it.
EXPECTED_EXCEPTION = {CASH_SHORT: "CASH_VARIANCE", NEAR_EXPIRY_BATCH: "EXPIRY_ALERT",
                      UNREPORTED_SHORT_DELIVERY: None, HIDDEN_SHRINK: None}

DAILY_MIX = (CASH_SHORT, CASH_SHORT, NEAR_EXPIRY_BATCH, UNREPORTED_SHORT_DELIVERY, HIDDEN_SHRINK)


@dataclass
class Incident:
    id: str
    type: str
    company: str
    branch: str
    day: int
    hour: int
    detail: dict
    warehouse_id: int = 0
    expected_exception: str = None


@dataclass
class Ledger:
    incidents: list = field(default_factory=list)

    def add(self, incident: Incident) -> None:
        incident.expected_exception = EXPECTED_EXCEPTION[incident.type]
        self.incidents.append(incident)

    def to_json(self) -> str:
        return json.dumps([asdict(i) for i in self.incidents], indent=2)

    def save(self, path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def load(path) -> "Ledger":
        return Ledger([Incident(**d) for d in json.loads(Path(path).read_text(encoding="utf-8"))])


def plan_incidents(plan, seed: int, day: int) -> list:
    """Five incidents per day on distinct initial branches. Perishable-only incidents go to companies that sell perishables."""
    r = rng.derive(seed, "incidents", day)
    initial = [(c, b) for c in plan.companies for b in c.branches if b.opens_hour == 0]
    r.shuffle(initial)
    used, out = set(), []
    for n, kind in enumerate(DAILY_MIX):
        for c, b in initial:
            if b.key in used:
                continue
            if kind == NEAR_EXPIRY_BATCH and not any(p.expiry for p in c.catalog):
                continue
            used.add(b.key)
            hour = {CASH_SHORT: 22, NEAR_EXPIRY_BATCH: 23, UNREPORTED_SHORT_DELIVERY: 10, HIDDEN_SHRINK: 14}[kind]
            if kind == CASH_SHORT:
                detail = {"amount": r.choice([100, 150, 200, 300, 400]), "staff": b.staff[0].key if b.staff else ""}
            elif kind == NEAR_EXPIRY_BATCH:
                detail = {"product_code": next(p.code for p in c.catalog if p.expiry), "units": r.randint(12, 24), "days_left": 2}
            elif kind == UNREPORTED_SHORT_DELIVERY:
                p = r.choice(c.catalog)
                detail = {"product_code": p.code, "units_recorded": 24, "units_arrived": 24 - r.randint(4, 9)}
            else:
                p = r.choice(c.catalog)
                detail = {"product_code": p.code, "units": r.randint(3, 8)}
            out.append(Incident(f"inc-d{day}-{n + 1}", kind, c.key, b.key, day, hour, detail))
            break
    return out

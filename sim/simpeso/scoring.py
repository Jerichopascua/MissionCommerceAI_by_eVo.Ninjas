"""Scoring: every injected incident is caught by PesoWeb, found by the AI, or undetected. Detection coverage is
(caught + ai_found) / injected. Matching is one-to-one, so one exception cannot account for two incidents."""
import json
from dataclasses import dataclass, field

CASH_TOLERANCE = 10      # pesos: the sim adds up to 5 of natural counting noise on top of an injected shortage


@dataclass
class Outcome:
    incident_id: str
    type: str
    branch: str
    status: str                 # caught | ai_found | undetected
    evidence_id: str = ""


@dataclass
class Scorecard:
    outcomes: list = field(default_factory=list)
    other_exceptions: list = field(default_factory=list)    # PesoWeb exceptions no incident explains

    def count(self, status: str) -> int:
        return sum(1 for o in self.outcomes if o.status == status)

    @property
    def injected(self) -> int:
        return len(self.outcomes)

    @property
    def coverage(self) -> float:
        return 0.0 if not self.outcomes else (self.count("caught") + self.count("ai_found")) / self.injected

    def summary(self) -> dict:
        by_type = {}
        for o in self.outcomes:
            by_type.setdefault(o.type, {"caught": 0, "ai_found": 0, "undetected": 0})[o.status] += 1
        return {"injected": self.injected, "caught": self.count("caught"), "ai_found": self.count("ai_found"),
                "undetected": self.count("undetected"), "coverage": round(self.coverage, 3),
                "other_exceptions": len(self.other_exceptions), "by_type": by_type}


def _variance(exc: dict):
    try:
        return float(json.loads(exc.get("evidenceJson") or "{}").get("variance"))
    except (TypeError, ValueError):
        return None


def _evidence_ok(incident, exc) -> bool:
    """Same amount for a cash shortage, same batch for an expiry alert (when the incident recorded one)."""
    if incident.type == "CASH_SHORT":
        v = _variance(exc)
        return v is None or abs(v + float(incident.detail["amount"])) <= CASH_TOLERANCE
    batch_id = incident.detail.get("batch_id")
    if incident.type == "NEAR_EXPIRY_BATCH" and batch_id:
        return exc.get("referenceNo") == f"batch-{batch_id}"
    return True


def score(incidents: list, exceptions: list, ai_findings=()) -> Scorecard:
    """incidents: ground-truth Incident objects. exceptions: PesoWeb Exception Center rows (camelCase JSON).
    ai_findings: dicts with `id`, `type` (incident type) and `branch` (branch key)."""
    card = Scorecard()
    used_exc, used_ai = set(), set()
    for inc in incidents:
        status, evidence = "undetected", ""
        if inc.expected_exception:
            for e in exceptions:
                if (e["id"] not in used_exc and e.get("type") == inc.expected_exception
                        and e.get("warehouseId") == inc.warehouse_id and _evidence_ok(inc, e)):
                    used_exc.add(e["id"])
                    status, evidence = "caught", str(e["id"])
                    break
        if status == "undetected":
            for f in ai_findings:
                if f["id"] not in used_ai and f.get("type") == inc.type and f.get("branch") == inc.branch:
                    used_ai.add(f["id"])
                    status, evidence = "ai_found", str(f["id"])
                    break
        card.outcomes.append(Outcome(inc.id, inc.type, inc.branch, status, evidence))
    card.other_exceptions = [e["id"] for e in exceptions if e["id"] not in used_exc]
    return card

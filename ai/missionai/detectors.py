"""Finding what PesoWeb cannot see. Short deliveries and silent stock loss leave no record in the POS, so the AI spends a
small counting budget where a loss would cost the most and is least likely to be explained: stock delivered without a
receiving report, then high-value fast movers. A count that comes back short becomes a finding, worded as "count differs
from system", never as an accusation. The finding's type is an inference (recent unreported delivery or not) and is
scored against the simulator's ground truth like everything else."""
from dataclasses import dataclass, field

UNREPORTED_SHORT_DELIVERY = "UNREPORTED_SHORT_DELIVERY"
HIDDEN_SHRINK = "HIDDEN_SHRINK"
UNREPORTED_WEIGHT = 1.0
BASELINE_WEIGHT = 0.15


@dataclass
class Target:
    warehouse_id: int
    product_id: int
    score: float
    reasons: list = field(default_factory=list)


def deliveries(receipts: list) -> list:
    """Receipts that are real deliveries: each SKU's first receipt at a branch is its opening stock, not a delivery."""
    first = {}
    for r in sorted(receipts, key=lambda r: r.get("id", 0)):
        first.setdefault((r["warehouseId"], r["productId"]), r.get("id", 0))
    return [r for r in receipts if r.get("id", 0) != first[(r["warehouseId"], r["productId"])]]


def rank_count_targets(receipts: list, sales_units: dict, unit_costs: dict, k: int, counted: set = frozenset()) -> list:
    """receipts: /api/ai/receipts rows. sales_units: {(warehouse, product): units sold}. unit_costs: {(warehouse, product): cost}.
    counted: (warehouse, product) pairs already counted. Returns the top k targets per warehouse."""
    scores, reasons = {}, {}
    fastest = max(sales_units.values(), default=0) or 1
    unreported = {}
    for r in deliveries(receipts):
        key = (r["warehouseId"], r["productId"])
        if not r.get("hasReceivingReport"):
            unreported[key] = unreported.get(key, 0.0) + float(r["quantity"]) * float(r.get("unitCost") or unit_costs.get(key, 0))
    for key in set(sales_units) | set(unit_costs) | set(unreported):
        if key in counted:
            continue
        velocity = sales_units.get(key, 0) / fastest
        value = float(unit_costs.get(key, 0)) * (1 + sales_units.get(key, 0))
        score = BASELINE_WEIGHT * value * (0.5 + velocity)
        why = ["high-value fast mover"] if score else []
        if key in unreported:
            score += UNREPORTED_WEIGHT * unreported[key]
            why = ["delivered without a receiving report"] + why
        if score > 0:
            scores[key], reasons[key] = score, why
    by_wh = {}
    for (wh, pid), s in scores.items():
        by_wh.setdefault(wh, []).append(Target(wh, pid, s, reasons[(wh, pid)]))
    out = []
    for wh in sorted(by_wh):
        out += sorted(by_wh[wh], key=lambda t: (-t.score, t.product_id))[:k]
    return out


def findings_from_counts(results: list, receipts: list, tolerance_units: float = 1.0) -> list:
    """results: dicts with warehouse_id, branch, product_id, system_qty, counted_qty. One finding per (warehouse, product)."""
    unreported_qty = {}
    for r in deliveries(receipts):
        if not r.get("hasReceivingReport"):
            key = (r["warehouseId"], r["productId"])
            unreported_qty[key] = unreported_qty.get(key, 0.0) + float(r["quantity"])
    seen, out = set(), []
    for c in results:
        key = (c["warehouse_id"], c["product_id"])
        shortfall = float(c["system_qty"]) - float(c["counted_qty"])
        if shortfall < tolerance_units or key in seen:
            continue
        seen.add(key)
        kind = UNREPORTED_SHORT_DELIVERY if unreported_qty.get(key, 0) >= shortfall else HIDDEN_SHRINK
        out.append({"id": f"f-{key[0]}-{key[1]}", "type": kind, "branch": c["branch"], "warehouse_id": key[0],
                    "product_id": key[1], "shortfall_units": shortfall,
                    "evidence": f"count differs from system by {shortfall:g} unit(s)"
                                + (" after a delivery with no receiving report" if kind == UNREPORTED_SHORT_DELIVERY else "")})
    return out

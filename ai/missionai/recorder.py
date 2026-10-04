"""Prediction recorder: the agent writes down what it expects BEFORE it acts; after the horizon the realized outcome
is attached. Calibration compares the model's error with a naive predictor that ignores the markdown (it assumes
sales stay at the no-markdown forecast), so the report says whether the price-response model adds anything."""
import json
from pathlib import Path


class PredictionRecorder:
    def __init__(self, path):
        self.path = Path(path)
        self.items = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec["type"] == "prediction":
                    self.items[rec["id"]] = rec
                else:
                    self.items[rec["id"]]["realized"] = rec["realized"]

    def _append(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def record(self, decision, at: str = "") -> str:
        b = decision.batch
        pid = f"p-{len(self.items) + 1}"
        rec = {"type": "prediction", "id": pid, "at": at, "warehouse_id": b.warehouse_id, "product_id": b.product_id,
               "batch_id": b.batch_id, "qty": b.qty, "unit_cost": b.unit_cost, "discount_pct": decision.discount_pct,
               "net_price": decision.net_price, "units": decision.mean_units, "units_lo": decision.lo_units,
               "units_hi": decision.hi_units, "margin": decision.margin, "waste_pesos": decision.waste_pesos,
               "baseline_units": decision.baseline_units, "baseline_waste_pesos": decision.baseline_waste_pesos,
               "reason": decision.reason}
        self.items[pid] = rec
        self._append(rec)
        return pid

    def resolve(self, pid: str, realized_units: float, avg_net_price: float) -> dict:
        rec = self.items[pid]
        if "realized" in rec:
            raise ValueError(f"{pid} is already resolved")
        units = min(float(realized_units), rec["qty"])
        realized = {"units": units, "avg_net_price": avg_net_price,
                    "margin": units * (avg_net_price - rec["unit_cost"]),
                    "waste_pesos": max(0.0, rec["qty"] - units) * rec["unit_cost"]}
        rec["realized"] = realized
        self._append({"type": "resolution", "id": pid, "realized": realized})
        return realized

    def resolved(self) -> list:
        return [r for r in self.items.values() if "realized" in r]

    def calibration(self) -> dict:
        rs = self.resolved()
        if not rs:
            return {"resolved": 0}
        n = len(rs)

        def mae(pred, actual):
            return sum(abs(pred(r) - actual(r)) for r in rs) / n

        model_units = mae(lambda r: r["units"], lambda r: r["realized"]["units"])
        naive_units = mae(lambda r: min(r["qty"], r["baseline_units"]), lambda r: r["realized"]["units"])
        model_waste = mae(lambda r: r["waste_pesos"], lambda r: r["realized"]["waste_pesos"])
        naive_waste = mae(lambda r: r["baseline_waste_pesos"], lambda r: r["realized"]["waste_pesos"])
        inside = sum(1 for r in rs if r["units_lo"] - 1e-9 <= r["realized"]["units"] <= r["units_hi"] + 1e-9) / n
        return {"resolved": n, "units_mae": model_units, "naive_units_mae": naive_units,
                "units_skill": (1 - model_units / naive_units) if naive_units > 0 else None,
                "waste_mae_pesos": model_waste, "naive_waste_mae_pesos": naive_waste,
                "margin_mae_pesos": mae(lambda r: r["margin"], lambda r: r["realized"]["margin"]),
                "interval_coverage": inside,
                "predicted_waste_pesos": sum(r["waste_pesos"] for r in rs),
                "realized_waste_pesos": sum(r["realized"]["waste_pesos"] for r in rs)}

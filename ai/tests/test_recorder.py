import tempfile
import unittest
from pathlib import Path

from missionai.optimizer import Batch, Decision
from missionai.recorder import PredictionRecorder


def decision(units=30.0, lo=24.0, hi=36.0, base_units=20.0, qty=40.0, cost=60.0, disc=20.0, price=80.0):
    b = Batch(1, 10, 100, "dairy", qty, cost, 100, 1, 12)
    return Decision(b, disc, price, price, units, lo, hi, units * (price - cost), (qty - units) * cost, base_units,
                    (qty - base_units) * cost, 10.0, "test")


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "preds.jsonl"

    def test_round_trip_and_reload_from_disk(self):
        r = PredictionRecorder(self.path)
        pid = r.record(decision())
        r.resolve(pid, 28, 80)
        again = PredictionRecorder(self.path)
        self.assertEqual(again.items[pid]["realized"]["units"], 28)
        self.assertEqual(again.items[pid]["units"], 30.0)

    def test_resolve_twice_is_rejected_and_unknown_id_fails(self):
        r = PredictionRecorder(self.path)
        pid = r.record(decision())
        r.resolve(pid, 28, 80)
        with self.assertRaises(ValueError):
            r.resolve(pid, 29, 80)
        with self.assertRaises(KeyError):
            r.resolve("nope", 1, 1)

    def test_realized_outcome_arithmetic_and_cap_at_quantity(self):
        r = PredictionRecorder(self.path)
        pid = r.record(decision(qty=40))
        out = r.resolve(pid, 55, 80)                       # cannot sell more than the batch held
        self.assertEqual(out["units"], 40)
        self.assertEqual(out["waste_pesos"], 0)
        self.assertEqual(out["margin"], 40 * (80 - 60))

    def test_calibration_hand_case(self):
        r = PredictionRecorder(self.path)
        a = r.record(decision(units=30, lo=24, hi=36, base_units=20))
        b = r.record(decision(units=30, lo=24, hi=36, base_units=20))
        r.resolve(a, 28, 80)          # model error 2, naive error 8, inside interval
        r.resolve(b, 38, 80)          # model error 8, naive error 18, outside interval
        c = r.calibration()
        self.assertEqual(c["resolved"], 2)
        self.assertAlmostEqual(c["units_mae"], 5.0)
        self.assertAlmostEqual(c["naive_units_mae"], 13.0)
        self.assertAlmostEqual(c["units_skill"], 1 - 5.0 / 13.0)
        self.assertAlmostEqual(c["interval_coverage"], 0.5)
        self.assertAlmostEqual(c["predicted_waste_pesos"], 2 * 10 * 60)

    def test_empty_store_is_safe(self):
        self.assertEqual(PredictionRecorder(self.path).calibration(), {"resolved": 0})

    def test_unresolved_predictions_do_not_count(self):
        r = PredictionRecorder(self.path)
        r.record(decision())
        self.assertEqual(r.calibration()["resolved"], 0)

    def test_ids_are_short_enough_for_the_pesoweb_prediction_ref(self):
        r = PredictionRecorder(self.path)
        for _ in range(3):
            self.assertLessEqual(len(r.record(decision())), 64)


if __name__ == "__main__":
    unittest.main()

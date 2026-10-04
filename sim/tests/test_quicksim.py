import unittest

import numpy as np
import torch

from simpeso import quicksim

SMALL = dict(individuals=4000, days=21, branches=4, skus=12, seed=3, device="cpu", anomalies=6)


class QuickSimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = quicksim.run(**SMALL)
        cls.b = quicksim.run(**SMALL)

    def test_same_seed_same_result_on_the_same_device(self):
        for key in ("events", "revenue_checksum", "forecast", "anomalies"):
            self.assertEqual(self.a[key], self.b[key])

    def test_a_different_seed_differs(self):
        self.assertNotEqual(quicksim.run(**{**SMALL, "seed": 4})["events"], self.a["events"])

    def test_it_reports_throughput_and_is_labelled_aggregated(self):
        self.assertGreater(self.a["events"], 1000)
        self.assertGreater(self.a["events_per_s"], 0)
        self.assertGreater(self.a["virtual_days_per_s"], 0)
        self.assertIn("aggregated", self.a["mode"])
        self.assertEqual(self.a["device"], "cpu")

    def test_price_aware_forecast_beats_seasonal_naive_when_prices_move(self):
        self.assertLess(self.a["forecast"]["model_wape"], self.a["forecast"]["naive_wape"])
        self.assertLess(self.a["forecast"]["price_slope"], 0)         # cheaper sells more

    def test_planted_anomalies_are_found_and_the_model_flags_fewer_cells_than_naive(self):
        an = self.a["anomalies"]
        self.assertEqual(an["planted"], 6)
        self.assertGreaterEqual(an["model_detector"]["found"], 3)
        self.assertLess(an["model_detector"]["flagged"], an["naive_detector"]["flagged"])

    def test_promos_raise_units_in_the_generated_data(self):
        sim = quicksim.simulate(4000, 21, 4, 12, 3, torch.device("cpu"))
        promo, plain = sim["ratio"] < 0.95, sim["ratio"] > 0.999
        self.assertGreater(sim["daily"][promo].mean(), sim["daily"][plain].mean() * 1.2)

    def test_planting_never_touches_training_days(self):
        daily = np.full((21, 3, 5), 100.0)
        truth = quicksim.plant_anomalies(daily, 14, 5, 1)
        self.assertTrue(all(t["day"] >= 14 for t in truth))
        self.assertTrue(np.all(daily[:14] == 100.0))

    def test_wape_and_detect_basics(self):
        self.assertEqual(quicksim.wape(np.array([1.0, 2.0]), np.array([1.0, 2.0])), 0.0)
        flags = quicksim.detect(np.array([100.0, 10.0]), np.array([10.0, 10.0]))
        self.assertEqual(flags.tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()

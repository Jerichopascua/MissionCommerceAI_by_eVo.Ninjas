import unittest
from dataclasses import replace

from missionai.demand import DemandModel
from missionai.optimizer import Batch, choose

POLICY = {"maxDiscountPct": 50, "hardMarginFloorPct": 5, "softMarginFloorPct": 15, "autonomyMode": "Autonomous"}


def batch(**kw):
    base = Batch(1, 10, 100, "dairy", qty=40, unit_cost=60, list_price=100, days_left=1, base_per_day=12)
    return replace(base, **kw)


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.model = DemandModel(prior_beta=-1.5)

    def test_overstocked_batch_gets_a_deeper_discount_than_a_light_one(self):
        heavy = choose(batch(qty=60), POLICY, self.model)
        light = choose(batch(qty=16), POLICY, self.model)
        self.assertGreater(heavy.discount_pct, light.discount_pct)
        self.assertGreater(heavy.discount_pct, 0)

    def test_no_markdown_when_the_stock_will_sell_anyway(self):
        d = choose(batch(qty=5), POLICY, self.model)
        self.assertEqual(d.discount_pct, 0)
        self.assertEqual(d.new_price, 100)

    def test_never_exceeds_the_policy_max_discount(self):
        d = choose(batch(qty=200, unit_cost=10), {**POLICY, "maxDiscountPct": 20}, self.model)
        self.assertLessEqual(d.discount_pct, 20)
        self.assertTrue(any(code == "EXCEEDS_MAX_DISCOUNT" for _, code in d.blocked))

    def test_never_prices_below_the_hard_floor_on_net_price(self):
        for cost in (30, 60, 80, 94):
            d = choose(batch(qty=300, unit_cost=cost), {**POLICY, "softMarginFloorPct": 5}, self.model)
            self.assertGreaterEqual(d.net_price, cost * 1.05 - 1e-9, cost)

    def test_net_price_uses_the_product_discount(self):
        d = choose(batch(qty=300, unit_cost=80, product_discount_pct=10), {**POLICY, "softMarginFloorPct": 5}, self.model)
        self.assertGreaterEqual(d.net_price, 80 * 1.05 - 1e-9)
        self.assertEqual(round(d.net_price, 2), round(d.new_price * 0.9, 2))

    def test_soft_floor_steps_are_skipped_and_reported(self):
        d = choose(batch(qty=300, unit_cost=80), POLICY, self.model)        # 15% over cost = 92
        self.assertGreaterEqual(d.net_price, 92 - 1e-9)
        self.assertTrue(any(code == "BELOW_SOFT_FLOOR" for _, code in d.blocked))

    def test_unknown_cost_blocks_every_markdown(self):
        d = choose(batch(qty=300, unit_cost=0), POLICY, self.model)
        self.assertEqual(d.discount_pct, 0)

    def test_prediction_matches_the_arithmetic(self):
        b = batch(qty=60)
        d = choose(b, POLICY, self.model)
        self.assertAlmostEqual(d.margin, d.mean_units * (d.net_price - b.unit_cost), places=6)
        self.assertAlmostEqual(d.waste_pesos, max(0, b.qty - d.mean_units) * b.unit_cost, places=6)
        self.assertLessEqual(d.lo_units, d.mean_units)
        self.assertGreaterEqual(d.hi_units, d.mean_units - 1e-9)

    def test_markdown_cuts_expected_waste_versus_no_markdown(self):
        d = choose(batch(qty=60), POLICY, self.model)
        self.assertLess(d.waste_pesos, d.baseline_waste_pesos)
        self.assertGreater(d.value_gain, 0)

    def test_more_hours_left_means_a_gentler_markdown(self):
        morning = choose(batch(qty=30), POLICY, self.model, hour=6)
        evening = choose(batch(qty=30), POLICY, self.model, hour=20)
        self.assertGreaterEqual(evening.discount_pct, morning.discount_pct)

    def test_stock_ahead_in_the_fefo_queue_leaves_less_demand_for_this_batch(self):
        alone = choose(batch(qty=30), POLICY, self.model)
        queued = choose(batch(qty=30, prior_qty=10), POLICY, self.model)
        self.assertGreaterEqual(queued.discount_pct, alone.discount_pct)
        self.assertLess(queued.baseline_units, alone.baseline_units)

    def test_deterministic(self):
        a = choose(batch(qty=45), POLICY, self.model)
        b = choose(batch(qty=45), POLICY, self.model)
        self.assertEqual((a.discount_pct, a.mean_units, a.margin), (b.discount_pct, b.mean_units, b.margin))


if __name__ == "__main__":
    unittest.main()

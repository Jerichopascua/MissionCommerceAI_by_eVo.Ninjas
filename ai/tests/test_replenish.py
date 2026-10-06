import math
import unittest

from missionai import replenish as rp


def prod(stock, pid=1, cost=10.0):
    return {"id": pid, "name": "Milk", "category": "Dairy", "stock": stock, "cost": cost}


class SuggestTests(unittest.TestCase):
    def test_stock_that_will_not_last_the_delivery_is_reordered_up_to_the_target(self):
        # 4 a day, no spread, 2 days to deliver, 7 days cover: reorder point 8, order up to 36
        s = rp.suggest(prod(6), 4.0, 0.0, 10, lead_days=2, cover_days=7)
        self.assertIsNotNone(s)
        self.assertEqual((s.suggested_qty, s.reorder_point), (30.0, 8.0))
        self.assertAlmostEqual(s.days_of_cover, 1.5)
        self.assertTrue(s.urgent)                                   # 1.5 days of cover, delivery takes 2

    def test_stock_above_the_reorder_point_needs_no_order(self):
        self.assertIsNone(rp.suggest(prod(20), 4.0, 0.0, 10, lead_days=2, cover_days=7))

    def test_no_sales_or_too_little_data_means_no_suggestion(self):
        self.assertIsNone(rp.suggest(prod(0), 0.0, 0.0, 10))
        self.assertIsNone(rp.suggest(prod(0), 4.0, 1.0, 2))

    def test_more_variable_demand_means_a_bigger_safety_allowance(self):
        calm = rp.suggest(prod(0), 4.0, 0.0, 10)
        wild = rp.suggest(prod(0), 4.0, 3.0, 10)
        self.assertGreater(wild.reorder_point, calm.reorder_point)
        self.assertGreater(wild.suggested_qty, calm.suggested_qty)

    def test_a_perishable_is_capped_at_what_sells_before_it_expires(self):
        # would be 36 without a cap; only 3 days of shelf life at 4 a day = 12
        s = rp.suggest(prod(0), 4.0, 0.0, 10, lead_days=2, cover_days=7, shelf_life_days=3)
        self.assertEqual(s.suggested_qty, 12.0)
        self.assertIn("expires", s.reason)

    def test_quantity_is_rounded_up_to_a_whole_pack(self):
        s = rp.suggest(prod(6), 4.0, 0.0, 10, lead_days=2, cover_days=7, pack=12)
        self.assertEqual(s.suggested_qty, 36.0)                     # 30 needed -> 3 packs of 12

    def test_confidence_reflects_how_many_days_of_sales_there_were(self):
        self.assertEqual(rp.suggest(prod(0), 4.0, 1.0, 14).confidence, "learned")
        self.assertEqual(rp.suggest(prod(0), 4.0, 1.0, 4).confidence, "limited")

    def test_not_urgent_when_the_stock_outlasts_the_delivery(self):
        s = rp.suggest(prod(9), 4.0, 0.0, 10, lead_days=2, cover_days=7)   # 2.25 days of cover, reorder point 8 -> above it
        self.assertIsNone(s)
        s = rp.suggest(prod(8), 4.0, 0.0, 10, lead_days=2, cover_days=7)   # exactly at the reorder point, 2 days of cover
        self.assertTrue(s.urgent)


class DemandTests(unittest.TestCase):
    def test_daily_demand_counts_zero_days(self):
        rate, sigma, n = rp.demand_from_daily([4, 0, 8, 4])
        self.assertEqual((rate, n), (4.0, 4))
        self.assertAlmostEqual(sigma, math.sqrt(8))

    def test_an_average_rate_alone_uses_the_poisson_spread(self):
        rate, sigma, n = rp.demand_poisson(9.0, 6)
        self.assertEqual((rate, sigma, n), (9.0, 3.0, 6))

    def test_no_data_is_zero(self):
        self.assertEqual(rp.demand_from_daily([]), (0.0, 0.0, 0))


class SuggestAllTests(unittest.TestCase):
    def test_most_urgent_first_and_products_without_demand_are_skipped(self):
        products = [prod(30, 1), prod(1, 2), prod(7, 3), prod(0, 4)]
        demand = lambda p: None if p["id"] == 4 else (4.0, 0.0, 10)
        out = rp.suggest_all(products, demand, lead_days=2, cover_days=7)
        self.assertEqual([s.product_id for s in out], [2, 3])        # product 1 has plenty, product 4 has no demand data
        self.assertTrue(out[0].urgent)

    def test_shelf_life_can_be_set_per_product(self):
        products = [prod(0, 1), prod(0, 2)]
        out = rp.suggest_all(products, lambda p: (4.0, 0.0, 10), lead_days=2, cover_days=7, shelf_life_for=lambda p: 3 if p["id"] == 1 else None)
        by = {s.product_id: s.suggested_qty for s in out}
        self.assertEqual(by, {1: 12.0, 2: 36.0})


if __name__ == "__main__":
    unittest.main()

import math
import random
import unittest

from missionai import price_test as pt


def poisson(rnd, lam):
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= limit:
            return k
        k += 1


def simulate(beta, seed, n_products=30, base_rate=6.0, days_base=5, days_test=7, ratio=1.10, common_shock=1.0, size_gap=2.0):
    """Treatment shops are `size_gap` times bigger than control shops; a common shock hits both in the test phase."""
    rnd = random.Random(seed)
    rows = []
    for p in range(n_products):
        r = {"product_id": p, "x": math.log(ratio)}
        r["treat_base"] = poisson(rnd, base_rate * size_gap * days_base)
        r["control_base"] = poisson(rnd, base_rate * days_base)
        r["treat_test"] = poisson(rnd, base_rate * size_gap * days_test * common_shock * ratio ** beta)
        r["control_test"] = poisson(rnd, base_rate * days_test * common_shock)
        rows.append(r)
    return rows


class DidTests(unittest.TestCase):
    def test_recovers_a_planted_sensitivity_inside_its_interval(self):
        hits = 0
        for seed in range(20):
            e = pt.did_estimate(simulate(-2.0, seed), 5, 7)
            hits += e["ci95"][0] <= -2.0 <= e["ci95"][1]
        self.assertGreaterEqual(hits, 17)                      # a 95% interval covers the truth about 19 times in 20

    def test_estimate_is_close_to_the_truth_on_average(self):
        betas = [pt.did_estimate(simulate(-1.5, s), 5, 7)["beta"] for s in range(30)]
        self.assertAlmostEqual(sum(betas) / len(betas), -1.5, delta=0.35)

    def test_common_shocks_and_shop_size_do_not_bias_the_answer(self):
        betas = [pt.did_estimate(simulate(-1.0, s, common_shock=1.4, size_gap=3.0), 5, 7)["beta"] for s in range(30)]
        self.assertAlmostEqual(sum(betas) / len(betas), -1.0, delta=0.4)

    def test_no_effect_gives_an_interval_that_contains_zero(self):
        e = pt.did_estimate(simulate(0.0, 3), 5, 7)
        self.assertLessEqual(e["ci95"][0], 0.0)
        self.assertGreaterEqual(e["ci95"][1], 0.0)

    def test_more_units_means_a_tighter_interval(self):
        small = pt.did_estimate(simulate(-1.5, 1, base_rate=1.0), 5, 7)
        big = pt.did_estimate(simulate(-1.5, 1, base_rate=12.0), 5, 7)
        self.assertLess(big["se"], small["se"])

    def test_sparse_data_is_flagged_as_unreliable(self):
        e = pt.did_estimate(simulate(-1.5, 1, n_products=3, base_rate=0.3), 5, 7)
        self.assertFalse(e["reliable"])

    def test_zero_counts_do_not_crash(self):
        rows = [{"product_id": 1, "x": 0.1, "treat_base": 0, "treat_test": 0, "control_base": 0, "control_test": 0}]
        e = pt.did_estimate(rows, 5, 7)
        self.assertIsNotNone(e["beta"])

    def test_products_with_no_price_change_are_ignored(self):
        e = pt.did_estimate([{"product_id": 1, "x": 0.0, "treat_base": 5, "treat_test": 5, "control_base": 5, "control_test": 5}], 5, 7)
        self.assertIsNone(e["beta"])
        self.assertEqual(e["products"], 0)

    def test_observations_scale_the_expected_units_by_the_control_trend(self):
        rows = [{"product_id": 1, "x": 0.1, "treat_base": 20, "treat_test": 18, "control_base": 10, "control_test": 14}]
        obs = pt.as_observations(rows, 5, 7)[0]
        # control rate went from 10/5 to 14/7 per day: a trend of ~1.0 after the +0.5 smoothing, so expected is near 7/5 * 20 = 28
        self.assertGreater(obs["expected_units"], 20)
        self.assertEqual(obs["units"], 18)


def simulate_switchback(beta, seed, n_products=30, base_rate=6.0, days_raised=7, days_normal=7, ratio=1.10):
    rnd = random.Random(seed)
    rows = []
    for p in range(n_products):
        rows.append({"product_id": p, "x": math.log(ratio), "raised_units": poisson(rnd, base_rate * days_raised * ratio ** beta),
                     "normal_units": poisson(rnd, base_rate * days_normal)})
    return rows


class SwitchbackTests(unittest.TestCase):
    def test_recovers_a_planted_sensitivity(self):
        betas = [pt.switchback_estimate(simulate_switchback(-1.8, s), 7, 7)["beta"] for s in range(30)]
        self.assertAlmostEqual(sum(betas) / len(betas), -1.8, delta=0.3)

    def test_interval_covers_the_truth_about_95_percent_of_the_time(self):
        hits = sum(pt.switchback_estimate(simulate_switchback(-1.5, s), 7, 7)["ci95"][0] <= -1.5 <= pt.switchback_estimate(simulate_switchback(-1.5, s), 7, 7)["ci95"][1] for s in range(40))
        self.assertGreaterEqual(hits, 34)

    def test_unequal_day_counts_are_handled(self):
        betas = [pt.switchback_estimate(simulate_switchback(-1.0, s, days_raised=5, days_normal=9), 5, 9)["beta"] for s in range(30)]
        self.assertAlmostEqual(sum(betas) / len(betas), -1.0, delta=0.35)

    def test_tighter_than_the_two_group_design_for_the_same_selling_volume(self):
        sw = pt.switchback_estimate(simulate_switchback(-1.5, 1, base_rate=6.0), 7, 7)["se"]
        did = pt.did_estimate(simulate(-1.5, 1, base_rate=6.0), 5, 7)["se"]
        self.assertLess(sw, did)

    def test_empty_and_unchanged_prices_are_safe(self):
        self.assertIsNone(pt.switchback_estimate([], 5, 5)["beta"])
        self.assertIsNone(pt.switchback_estimate([{"product_id": 1, "x": 0.0, "raised_units": 3, "normal_units": 3}], 5, 5)["beta"])


class RandomizedDaysTests(unittest.TestCase):
    def test_pairs_are_balanced_and_deterministic(self):
        a = pt.randomized_days(10, 3)
        self.assertEqual(a, pt.randomized_days(10, 3))
        self.assertEqual(sum(a), 5)
        for i in range(0, 10, 2):
            self.assertEqual(a[i] + a[i + 1], 1)

    def test_odd_length_still_returns_that_many_days(self):
        self.assertEqual(len(pt.randomized_days(7, 1)), 7)

    def test_different_seeds_give_different_orders(self):
        self.assertTrue(any(pt.randomized_days(12, s) != pt.randomized_days(12, 0) for s in range(1, 6)))


if __name__ == "__main__":
    unittest.main()

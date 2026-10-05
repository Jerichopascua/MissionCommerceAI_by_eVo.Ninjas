import math
import random
import unittest

from missionai.demand import DemandModel


def poisson(rnd, lam):
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= limit:
            return k
        k += 1


class DemandTests(unittest.TestCase):
    def test_recovers_a_planted_elasticity(self):
        rnd = random.Random(5)
        m = DemandModel()
        for _ in range(300):
            ratio = rnd.choice([1.0, 0.9, 0.75, 0.6])
            m.observe("snacks", 8.0, ratio, poisson(rnd, 8.0 * ratio ** -2.2))
        self.assertAlmostEqual(m.beta("snacks"), -2.2, delta=0.25)

    def test_no_data_returns_the_prior(self):
        self.assertEqual(DemandModel(prior_beta=-1.1).beta("x"), -1.1)

    def test_observations_at_list_price_carry_no_slope_information(self):
        m = DemandModel()
        for _ in range(50):
            m.observe("x", 5.0, 1.0, 5)
        self.assertEqual(m.beta("x"), m.prior_beta)

    def test_small_noisy_samples_stay_near_the_prior(self):
        m = DemandModel(prior_beta=-1.3, prior_weight=3.0)
        m.observe("x", 3.0, 0.8, 0)       # one unlucky window
        m.observe("x", 3.0, 0.8, 1)
        self.assertGreater(m.beta("x"), -1.3 - 1.0)
        self.assertLess(m.beta("x"), -1.3 + 1.0)

    def test_categories_are_independent(self):
        rnd = random.Random(1)
        m = DemandModel()
        for _ in range(200):
            r = rnd.choice([1.0, 0.7])
            m.observe("a", 8.0, r, poisson(rnd, 8.0 * r ** -3.0))
            m.observe("b", 8.0, r, poisson(rnd, 8.0 * r ** -0.5))
        self.assertLess(m.beta("a"), m.beta("b") - 1.5)

    def test_interval_contains_mean_and_widens_with_it(self):
        m = DemandModel()
        mean1, lo1, hi1 = m.expected_units("x", 4.0, 1.0, 1, 6)
        mean2, lo2, hi2 = m.expected_units("x", 40.0, 1.0, 1, 6)
        self.assertTrue(lo1 <= mean1 <= hi1 and lo2 <= mean2 <= hi2)
        self.assertGreater(hi2 - lo2, hi1 - lo1)

    def test_discount_raises_expected_units_when_beta_is_negative(self):
        m = DemandModel(prior_beta=-1.5)
        full = m.expected_units("x", 10.0, 1.0, 1, 6)[0]
        cheap = m.expected_units("x", 10.0, 0.7, 1, 6)[0]
        self.assertGreater(cheap, full * 1.5)

    def test_share_left_is_one_at_open_zero_after_close_and_monotone(self):
        m = DemandModel()
        self.assertAlmostEqual(m.share_left(6), 1.0)
        self.assertEqual(m.share_left(24), 0.0)
        shares = [m.share_left(h) for h in range(6, 25)]
        self.assertEqual(shares, sorted(shares, reverse=True))

    def test_fitted_hour_profile_moves_the_share(self):
        m = DemandModel()
        m.fit_hours({7: 50, 8: 50, 18: 5, 19: 5})            # a morning shop
        self.assertLess(m.share_left(12), 0.15)
        self.assertGreater(m.share_left(6), 0.99)

    def test_a_bigger_prior_share_keeps_late_hours_possible(self):
        tight, loose = DemandModel(), DemandModel()
        tight.fit_hours({18: 50, 19: 50})
        loose.fit_hours({18: 50, 19: 50}, prior_share=0.5)
        self.assertLess(tight.share_left(21), 0.01)
        self.assertGreater(loose.share_left(21), 0.05)
        self.assertGreater(loose.share_left(21), 10 * tight.share_left(21))

    def test_a_precise_price_test_moves_the_slope_and_a_noisy_one_barely_does(self):
        precise, noisy, none = DemandModel(prior_beta=-1.3), DemandModel(prior_beta=-1.3), DemandModel(prior_beta=-1.3)
        precise.add_estimate("x", -2.5, 0.1)
        noisy.add_estimate("x", -3.9, 2.25)
        self.assertAlmostEqual(precise.beta("x"), -2.5, delta=0.05)
        self.assertGreater(noisy.beta("x"), -1.8)                 # pulled only a little toward the noisy number
        self.assertLess(noisy.beta("x"), -1.3)
        self.assertEqual(none.beta("x"), -1.3)

    def test_estimates_are_per_category_and_stay_inside_the_bounds(self):
        m = DemandModel()
        m.add_estimate("a", -50.0, 0.01)
        self.assertEqual(m.beta("a"), -6.0)
        self.assertEqual(m.beta("b"), m.prior_beta)

    def test_more_days_left_means_more_expected_units(self):
        m = DemandModel()
        self.assertGreater(m.expected_units("x", 5.0, 1.0, 3, 6)[0], m.expected_units("x", 5.0, 1.0, 1, 6)[0] * 2.5)


if __name__ == "__main__":
    unittest.main()

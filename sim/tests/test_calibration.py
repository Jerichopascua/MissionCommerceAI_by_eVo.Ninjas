import unittest

from simpeso import behavior, calibration as cal, world

# a synthetic "real" profile: a late-evening store (no real data is stored in the repo)
REAL = {"hour_share": {"0": 0.15, "8": 0.02, "12": 0.05, "18": 0.08, "20": 0.15, "21": 0.2, "22": 0.2, "23": 0.15}}


def evening(visits):
    return sum(1 for v in visits if v.hour >= 20) / len(visits)


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = world.plan_group(21, "starter")
        cls.people = behavior.make_individuals(cls.plan, 21)
        cls.c = cal.from_real(REAL, weight=0.6)

    def test_hour_share_is_renormalised_inside_trading_hours_and_outside_share_is_reported(self):
        self.assertAlmostEqual(sum(self.c.hour_share), 1.0)
        self.assertEqual(len(self.c.hour_share), behavior.CLOSE_H - behavior.OPEN_H)
        self.assertEqual(self.c.outside_hours_share, 0.15)       # the 00:00 sales the simulator cannot place

    def test_blend_is_a_proper_distribution(self):
        arch = [1.0 / 18] * 18
        b = self.c.blend(arch)
        self.assertAlmostEqual(sum(b), 1.0)
        self.assertEqual(cal.Calibration(tuple([1 / 18] * 18), 0.0).blend(arch), arch)       # weight 0 = archetype only

    def test_calibration_moves_arrivals_toward_the_real_evening_peak(self):
        base = behavior.day_arrivals(self.plan, self.people, 2, 21)
        tuned = behavior.day_arrivals(self.plan, self.people, 2, 21, calib=self.c)
        self.assertGreater(evening(tuned), evening(base) + 0.1)

    def test_basket_scale_shrinks_baskets(self):
        small = cal.Calibration(self.c.hour_share, 0.0, 0.5)
        full = sum(len(v.lines) for v in behavior.day_visits(self.plan, self.people, 2, 21))
        half = sum(len(v.lines) for v in behavior.day_visits(self.plan, self.people, 2, 21, calib=small))
        self.assertLess(half, full * 0.8)

    def test_default_behavior_is_unchanged_without_a_calibration(self):
        a = behavior.day_visits(self.plan, self.people, 3, 21)
        b = behavior.day_visits(self.plan, self.people, 3, 21, calib=None)
        self.assertEqual(a, b)

    def test_fit_basket_scale_brings_lines_per_visit_to_the_target(self):
        scale = cal.fit_basket_scale(self.plan, self.people, 21, real_lines_per_sale=2.0)
        c = cal.Calibration(tuple([1 / 18] * 18), 0.0, scale)
        visits = behavior.day_visits(self.plan, self.people, 1, 21, calib=c)
        mean = sum(len(v.lines) for v in visits) / len(visits)
        self.assertLess(abs(mean - 2.0) / 2.0, 0.15)
        self.assertGreaterEqual(scale, 0.3)
        self.assertLessEqual(scale, 1.5)

    def test_no_real_sales_in_trading_hours_is_an_error(self):
        with self.assertRaises(ValueError):
            cal.from_real({"hour_share": {"1": 1.0}})


if __name__ == "__main__":
    unittest.main()

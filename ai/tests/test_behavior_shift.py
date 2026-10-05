import random
import unittest

from missionai import behavior_shift as bs


def day_events(day, hours, price, list_price=250, qty=1):
    return [{"day": day, "hour": h, "price": price, "list_price": list_price, "qty": qty} for h in hours]


class ShiftTests(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(3)
        self.before = [e for d in range(3) for e in day_events(d, [18 + rnd.random() * 2 for _ in range(8)], 250)]
        self.after_shifted = [e for d in range(3, 8) for e in day_events(d, [20.6 + rnd.random() * 1.0 for _ in range(10)], 125)]
        self.after_same = [e for d in range(3, 8) for e in day_events(d, [18 + rnd.random() * 2 for _ in range(8)], 250)]

    def test_detects_a_real_shift_to_clearance_time(self):
        r = bs.detect_shift(self.before + self.after_shifted, range(3), range(3, 8), seed=1)
        self.assertTrue(r["shifted"])
        self.assertGreater(r["mean_hour_shift"], 1.5)
        self.assertLess(r["p_value"], 0.01)
        self.assertEqual(r["before"]["discount_share"], 0)
        self.assertEqual(r["after"]["discount_share"], 1)
        self.assertIn("later", r["verdict"])

    def test_no_shift_is_not_reported_as_one(self):
        r = bs.detect_shift(self.before + self.after_same, range(3), range(3, 8), seed=1)
        self.assertFalse(r["shifted"])
        self.assertEqual(r["verdict"], "No reliable change in when customers buy.")

    def test_full_price_and_discount_units_are_split_by_the_95_percent_rule(self):
        ev = day_events(0, [19, 19], 250) + day_events(0, [21], 125, qty=3) + day_events(0, [21], 240)
        p = bs._period(ev, {0})
        self.assertEqual(p["units_per_day"], 6)
        self.assertEqual(p["discount_units_per_day"], 3)
        self.assertEqual(p["full_price_units_per_day"], 3)       # 240 is within 5% of list

    def test_full_price_change_shows_cannibalization(self):
        before = day_events(0, [19] * 6, 250)
        after = day_events(1, [19] * 2, 250) + day_events(1, [21] * 6, 125)
        r = bs.detect_shift(before + after, [0], [1], seed=1)
        self.assertEqual(r["full_price_change_per_day"], -4)

    def test_quantity_weights_the_hours(self):
        ev = day_events(0, [20], 125, qty=3) + day_events(0, [18], 250, qty=1)
        self.assertEqual(sorted(bs._hours(ev)), [18, 20, 20, 20])

    def test_empty_periods_are_safe(self):
        r = bs.detect_shift([], [0], [1])
        self.assertFalse(r["shifted"])
        self.assertIsNone(r["mean_hour_shift"])

    def test_deterministic_for_a_seed(self):
        a = bs.detect_shift(self.before + self.after_shifted, range(3), range(3, 8), seed=5)
        b = bs.detect_shift(self.before + self.after_shifted, range(3), range(3, 8), seed=5)
        self.assertEqual(a["p_value"], b["p_value"])


if __name__ == "__main__":
    unittest.main()

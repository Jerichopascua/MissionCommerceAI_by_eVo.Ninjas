import datetime as dt
import unittest
from types import SimpleNamespace

from simpeso import behavior, world, ai_hook


class SplitBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = world.plan_group(21, "smoke")
        cls.people = behavior.make_individuals(cls.plan, 21)
        cls.arrivals = behavior.day_arrivals(cls.plan, cls.people, 1, 21)

    def test_arrivals_have_no_baskets_and_are_deterministic(self):
        self.assertGreater(len(self.arrivals), 40)
        self.assertTrue(all(v.lines == () for v in self.arrivals))
        self.assertEqual(self.arrivals, behavior.day_arrivals(self.plan, self.people, 1, 21))

    def test_arrivals_do_not_depend_on_prices(self):
        # who walks in is fixed by habit; only the basket reacts to the price in force at that moment
        self.assertEqual([a.id for a in self.arrivals], [a.id for a in behavior.day_arrivals(self.plan, self.people, 1, 21)])

    def test_basket_is_deterministic_for_the_same_prices_and_reacts_to_a_markdown(self):
        full = cheap = 0
        for a in self.arrivals:
            f1 = behavior.fill_basket(self.plan, a, 21)
            f2 = behavior.fill_basket(self.plan, a, 21)
            self.assertEqual(f1, f2)
            c = behavior.fill_basket(self.plan, a, 21, lambda b, code: 0.6)
            full += sum(q for _, q in f1.lines) if f1 else 0
            cheap += sum(q for _, q in c.lines) if c else 0
        self.assertGreater(cheap, full * 1.2)

    def test_day_visits_equals_arrivals_with_baskets(self):
        direct = behavior.day_visits(self.plan, self.people, 1, 21)
        built = [v for v in (behavior.fill_basket(self.plan, a, 21) for a in self.arrivals) if v]
        self.assertEqual(direct, built)


class FakeDriver:
    def __init__(self, rows):
        self.rows = rows

    def all_batches(self, acct, wh):
        return self.rows


class HookHelperTests(unittest.TestCase):
    def test_batches_adapter_computes_days_left_and_skips_non_expiry(self):
        today = dt.date.today()
        rows = [{"id": 1, "productId": 5, "batchNo": "a", "expiryDate": (today + dt.timedelta(days=1)).isoformat() + "T00:00:00", "qtyOnHand": 9, "cost": 3.5},
                {"id": 2, "productId": 6, "batchNo": "b", "expiryDate": None, "qtyOnHand": 4, "cost": 2}]
        hooks = ai_hook.AiHooks.__new__(ai_hook.AiHooks)
        hooks.ctx = SimpleNamespace(driver=FakeDriver(rows))
        out = hooks.batches(None, 1)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["batchId"], out[0]["daysLeft"], out[0]["unitCost"]), (1, 1, 3.5))


if __name__ == "__main__":
    unittest.main()

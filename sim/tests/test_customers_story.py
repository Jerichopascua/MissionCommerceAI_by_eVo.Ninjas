import statistics
import unittest

from simpeso import customers as cu, story


class FakeShop:
    def __init__(self, cut=20.5, lot=12, cuts=()):
        self.cut, self.lot, self.left, self.h, self.cuts = cut, lot, lot, 17.0, list(cuts)

    def tick(self, h):
        self.h = h

    def price(self):
        return 125.0 if (self.cut is not None and self.h >= self.cut) else 250.0

    def stock(self):
        return self.left

    def buy(self, q):
        self.left -= q
        return self.price() * q

    def cashier_hint(self):
        return statistics.median(self.cuts) if self.cuts else None


def person(stress=0.9, thrift=0.9, patience=0.8, soc=0.8, need=1.0, habit=21.0, max_buy=3, adaptive=True):
    return cu.Customer("c", "Test", cu.Traits(stress, thrift, patience, soc, need, habit, max_buy), adaptive)


def obs(hour, price, stock=10):
    return cu.Observation(hour, price, 250.0, stock)


class JudgementTests(unittest.TestCase):
    def setUp(self):
        import random
        self.rnd = random.Random(1)

    def test_a_squeezed_customer_cannot_pay_full_price_but_buys_at_half(self):
        c = person(stress=0.9)
        c.start_night(0, self.rnd, 250.0)
        self.assertLess(c.wtp, 250 * 0.9)
        self.assertNotEqual(c.decide(obs(19, 250), self.rnd)[0], "buy")
        self.assertEqual(c.decide(obs(21, 125), self.rnd)[0], "buy")

    def test_a_comfortable_customer_pays_full_price(self):
        c = person(stress=0.0, thrift=0.2)
        c.start_night(0, self.rnd, 250.0)
        self.assertEqual(c.decide(obs(19, 250), self.rnd)[0], "buy")

    def test_a_bargain_makes_a_thrifty_customer_take_extra_but_not_more_than_stock(self):
        c = person(thrift=1.0, max_buy=3)
        c.start_night(0, self.rnd, 250.0)
        self.assertEqual(c.decide(obs(21, 125, stock=10), self.rnd), ("buy", 3))
        self.assertEqual(c.decide(obs(21, 125, stock=2), self.rnd), ("buy", 2))

    def test_a_comfortable_bargain_hunter_who_trusts_the_cut_waits_instead_of_paying_full_price(self):
        hunter = person(stress=0.0, thrift=0.9, patience=0.8)
        hunter.start_night(0, self.rnd, 250.0)
        self.assertEqual(hunter.decide(obs(19.5, 250), self.rnd)[0], "buy")          # does not know about a cut yet
        hunter.told(20.5, "cashier")
        self.assertEqual(hunter.decide(obs(19.5, 250), self.rnd)[0], "wait")
        easy = person(stress=0.0, thrift=0.2)
        easy.start_night(0, self.rnd, 250.0)
        easy.told(20.5, "cashier")
        self.assertEqual(easy.decide(obs(19.5, 250), self.rnd)[0], "buy")           # not a bargain hunter: pays

    def test_nothing_in_stock_means_leave(self):
        c = person()
        c.start_night(0, self.rnd, 250.0)
        self.assertEqual(c.decide(obs(21, 125, stock=0), self.rnd)[0], "leave")

    def test_without_any_belief_they_ask_the_cashier_then_leave(self):
        c = person()
        c.start_night(0, self.rnd, 250.0)
        self.assertEqual(c.decide(obs(19, 250), self.rnd)[0], "ask")
        c.asked = True
        self.assertEqual(c.decide(obs(19, 250), self.rnd)[0], "leave")

    def test_with_a_belief_they_wait_if_the_wait_is_short_enough(self):
        c = person(patience=0.8)
        c.start_night(0, self.rnd, 250.0)
        c.told(20.5, "cashier")
        self.assertEqual(c.decide(obs(19.5, 250), self.rnd)[0], "wait")
        self.assertEqual(c.decide(obs(17.0, 250), self.rnd)[0], "leave")        # 3.5 h is too long for them

    def test_an_impatient_customer_does_not_wait_long(self):
        c = person(patience=0.2)
        c.start_night(0, self.rnd, 250.0)
        c.told(20.5, "cashier")
        self.assertEqual(c.decide(obs(19.5, 250), self.rnd)[0], "leave")

    def test_a_belief_that_keeps_failing_loses_confidence(self):
        c = person()
        c.start_night(0, self.rnd, 250.0)
        c.told(20.5, "cashier")
        before = c.conf
        c.decide(obs(22.0, 250), self.rnd)
        self.assertLess(c.conf, before)

    def test_seeing_a_cut_builds_a_belief_and_a_second_sighting_strengthens_it(self):
        c = person()
        c.saw_cut(20.5, exact=True)
        first = c.conf
        c.saw_cut(20.5, exact=True)
        self.assertEqual(c.cut_hour, 20.5)
        self.assertGreater(c.conf, first)

    def test_a_friend_tip_only_fills_a_weak_belief(self):
        c = person()
        c.told(20.5, "a friend")
        self.assertEqual(c.conf, 0.4)
        c.saw_cut(21.0, exact=True)
        c.conf = 0.9
        c.told(18.0, "a friend")
        self.assertNotEqual(c.cut_hour, 18.0)

    def test_arrival_moves_toward_the_cut_once_they_know_about_it(self):
        c = person(habit=21.0)
        c.start_night(0, self.rnd, 250.0)
        habit_arrival = c.arrival
        c.told(20.5, "cashier")
        c.start_night(1, self.rnd, 250.0)
        self.assertLess(c.arrival, 20.5)
        self.assertNotEqual(c.arrival, habit_arrival)

    def test_missing_out_makes_them_come_earlier(self):
        c = person()
        c.told(20.5, "cashier")
        c.start_night(0, self.rnd, 250.0)
        a1 = c.arrival
        c.missed_out(21.0)
        c.start_night(1, self.rnd, 250.0)
        self.assertLessEqual(c.arrival, a1)

    def test_non_adaptive_customers_never_learn(self):
        c = person(adaptive=False)
        c.saw_cut(20.5, exact=True)
        c.told(20.5, "cashier")
        c.missed_out(21.0)
        self.assertIsNone(c.cut_hour)
        self.assertEqual(c.conf, 0.0)
        c.start_night(0, self.rnd, 250.0)
        self.assertEqual(c.decide(obs(19, 250), self.rnd)[0], "leave")


class PopulationTests(unittest.TestCase):
    def test_deterministic_and_marco_is_squeezed_with_squeezed_friends(self):
        a, b = cu.build_population(3), cu.build_population(3)
        self.assertEqual([p.traits for p in a], [p.traits for p in b])
        marco = a[0]
        self.assertEqual(marco.name, "Marco")
        self.assertGreater(marco.traits.budget_stress, 0.8)
        self.assertTrue(marco.friends and all(f.traits.budget_stress > 0.65 for f in marco.friends))

    def test_mix_of_situations(self):
        stress = [p.traits.budget_stress for p in cu.build_population(3)]
        self.assertTrue(min(stress) < 0.2 and max(stress) > 0.8)


class NightTests(unittest.TestCase):
    def week(self, adaptive, days=10):
        people = cu.build_population(3, adaptive=adaptive)
        out, cuts = [], []
        for d in range(days):
            shop = FakeShop(cut=20.5 if d >= 3 else None, cuts=cuts)
            r = story.run_night(people, shop, d, 3)
            if r["cut_hour"]:
                cuts.append(r["cut_hour"])
            out.append((r, shop))
        return people, out

    def test_nobody_is_told_in_advance_no_cut_means_no_clearance_buying(self):
        _, nights = self.week(True)
        for r, _ in nights[:3]:
            self.assertTrue(all(e["price"] >= 237 for e in r["events"]))
            self.assertEqual(r["tips"], 0)

    def test_learning_customers_shift_toward_the_clearance_hour(self):
        _, nights = self.week(True)
        early = [e["hour"] for r, _ in nights[3:5] for e in r["events"]]
        late = [e["hour"] for r, _ in nights[7:] for e in r["events"]]
        self.assertGreater(statistics.mean(late), statistics.mean(early) - 0.01)
        self.assertGreater(sum(r["waited"] for r, _ in nights[5:]), 0)
        self.assertGreater(sum(r["tips"] for r, _ in nights), 0)

    def test_naive_customers_never_wait(self):
        _, nights = self.week(False)
        self.assertEqual(sum(r["waited"] for r, _ in nights), 0)

    def test_learning_customers_clear_more_stock_than_naive_ones(self):
        _, learn = self.week(True)
        _, naive = self.week(False)
        sold = lambda ns: sum(12 - s.left for _, s in ns[5:])
        self.assertGreater(sold(learn), sold(naive))

    def test_full_price_sales_fall_when_customers_learn_to_wait(self):
        _, learn = self.week(True, days=12)
        _, naive = self.week(False, days=12)
        full = lambda ns: sum(e["qty"] for r, _ in ns[6:] for e in r["events"] if e["price"] >= 237)
        self.assertLess(full(learn), full(naive))

    def test_marco_waits_buys_extra_and_tells_friends(self):
        people, _ = self.week(True)
        text = " ".join(t for _, _, t in people[0].diary)
        self.assertIn("I will wait", text)
        self.assertIn("a bargain, so I took extra", text)
        self.assertIn("told", text)

    def test_stock_never_goes_negative_and_nobody_buys_after_closing(self):
        _, nights = self.week(True)
        for r, s in nights:
            self.assertGreaterEqual(s.left, 0)
            self.assertTrue(all(cu.OPEN <= e["hour"] < cu.CLOSE for e in r["events"]))

    def test_deterministic(self):
        _, a = self.week(True)
        _, b = self.week(True)
        self.assertEqual([r["events"] for r, _ in a], [r["events"] for r, _ in b])


if __name__ == "__main__":
    unittest.main()

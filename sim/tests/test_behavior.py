import re
import unittest
from pathlib import Path
from simpeso import archetypes, behavior, world

SIMPESO = Path(__file__).resolve().parent.parent / "simpeso"


def units(visits, branch=None):
    return sum(q for v in visits if branch in (None, v.branch) for _, q in v.lines)


class BehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = world.plan_group(21, "starter")
        cls.people = behavior.make_individuals(cls.plan, 21)

    def test_visits_are_deterministic_per_seed_and_day(self):
        a = behavior.day_visits(self.plan, self.people, 2, 21)
        b = behavior.day_visits(self.plan, self.people, 2, 21)
        self.assertEqual(a, b)
        self.assertNotEqual(a, behavior.day_visits(self.plan, self.people, 3, 21))
        self.assertGreater(len(a), 50)

    def test_individuals_persist_and_keep_home_branch(self):
        again = behavior.make_individuals(self.plan, 21)
        self.assertEqual(self.people, again)
        homes = {p.id: p.home_branch for p in self.people}
        for day in (0, 1, 2, 3):
            for v in behavior.day_visits(self.plan, self.people, day, 21):
                if not v.shopper.startswith("walkin"):
                    self.assertEqual(homes[v.shopper], v.branch)

    def test_regulars_come_back_across_days(self):
        seen = {}
        for day in range(7):
            for v in behavior.day_visits(self.plan, self.people, day, 21):
                seen.setdefault(v.shopper, set()).add(day)
        self.assertTrue(any(len(d) >= 3 for d in seen.values()))

    def test_a_discount_raises_expected_units(self):
        base = sum(units(behavior.day_visits(self.plan, self.people, d, 21)) for d in range(7))
        cheap = sum(units(behavior.day_visits(self.plan, self.people, d, 21, lambda b, c: 0.7)) for d in range(7))
        dear = sum(units(behavior.day_visits(self.plan, self.people, d, 21, lambda b, c: 1.3)) for d in range(7))
        self.assertGreater(cheap, base * 1.15)
        self.assertLess(dear, base)

    def test_high_elasticity_archetypes_respond_more_than_low(self):
        lib = behavior._library()
        def lift(group):
            n0 = n1 = 0
            for d in range(7):
                v0 = behavior.day_visits(self.plan, self.people, d, 21)
                v1 = behavior.day_visits(self.plan, self.people, d, 21, lambda b, c: 0.7)
                n0 += sum(q for v in v0 if group(lib[v.archetype]) for _, q in v.lines)
                n1 += sum(q for v in v1 if group(lib[v.archetype]) for _, q in v.lines)
            return n1 / max(1, n0)
        high = lift(lambda a: a.price_response >= 2.0)
        low = lift(lambda a: a.price_response <= 0.8)
        self.assertGreater(high, low)

    def test_evening_and_morning_missions_differ(self):
        lib = behavior._library()
        hours = {"morning": [], "evening": []}
        for d in range(5):
            for v in behavior.day_visits(self.plan, self.people, d, 21):
                t = lib[v.archetype].time
                if t in hours:
                    hours[t].append(v.hour)
        self.assertGreater(sum(hours["evening"]) / len(hours["evening"]), sum(hours["morning"]) / len(hours["morning"]) + 6)

    def test_new_branch_has_no_visits_before_it_opens(self):
        exp = self.plan.expansions[0]
        for v in behavior.day_visits(self.plan, self.people, 0, 21):
            if v.branch == exp["branch"]:
                self.assertGreaterEqual(v.hour, exp["hour"])

    def test_price_response_is_not_used_outside_behavior(self):
        for path in SIMPESO.glob("*.py"):
            if path.name in ("behavior.py", "archetypes.py"):
                continue
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"price_response|elasticity", path.name)


if __name__ == "__main__":
    unittest.main()

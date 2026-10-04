import unittest
from simpeso import world


class WorldPlanTests(unittest.TestCase):
    def test_same_seed_same_hash_and_different_seed_differs(self):
        a = world.plan_hash(world.plan_group(11, "starter"))
        b = world.plan_hash(world.plan_group(11, "starter"))
        c = world.plan_hash(world.plan_group(12, "starter"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_group_has_five_companies_with_distinct_verticals(self):
        plan = world.plan_group(1, "starter")
        self.assertEqual(len(plan.companies), 5)
        self.assertEqual(len({c.vertical for c in plan.companies}), 5)

    def test_every_plan_respects_the_tier_limits(self):
        lim = world.BUSINESS_TIER
        for profile in ("smoke", "starter"):
            for seed in range(1, 30):
                plan = world.plan_group(seed, profile)
                for c in plan.companies:
                    self.assertLessEqual(len(c.branches), lim["branches"], (seed, c.key))
                    staff = sum(len(b.staff) for b in c.branches)
                    self.assertLessEqual(staff + 1, lim["users"], (seed, c.key))
                    self.assertLessEqual(len(c.catalog), lim["products"])
                    self.assertGreaterEqual(len(c.catalog), 1)

    def test_expiry_reason_when_vertical_has_no_expiry(self):
        plan = world.plan_group(2, "starter")
        for c in plan.companies:
            has_expiry = any(p.expiry for p in c.catalog)
            self.assertTrue(has_expiry or c.expiry_reason, c.key)

    def test_a_branch_opens_mid_run_in_every_seed_and_never_exceeds_the_cap(self):
        for profile in ("smoke", "starter"):
            for seed in range(1, 40):
                plan = world.plan_group(seed, profile)
                self.assertGreaterEqual(len(plan.expansions), 1, (profile, seed))
                for e in plan.expansions:
                    self.assertTrue(11 <= e["hour"] <= 15)
                for c in plan.companies:
                    self.assertLessEqual(len(c.branches), world.BUSINESS_TIER["branches"])

    def test_starter_has_about_twenty_branches(self):
        plan = world.plan_group(3, "starter")
        total = sum(len(c.branches) for c in plan.companies)
        self.assertTrue(14 <= total <= 25, total)

    def test_logins_are_unique_and_staff_have_traits(self):
        plan = world.plan_group(5, "starter")
        emails = [c.owner.email for c in plan.companies] + [s.email for c in plan.companies for b in c.branches for s in b.staff]
        self.assertEqual(len(emails), len(set(emails)))
        for c in plan.companies:
            for b in c.branches:
                self.assertGreaterEqual(len(b.staff), 1)
                self.assertEqual(b.staff[0].role, "Cashier")
                for s in b.staff:
                    self.assertTrue(0 < s.speed <= 1 and 0.8 <= s.accuracy <= 1)
                    self.assertGreaterEqual(len(s.password), 6)

    def test_no_accusation_wording_in_generated_text(self):
        plan = world.plan_group(7, "starter")
        text = " ".join(str(v) for v in world.to_dict(plan).values()).lower()
        for bad in ("thief", "theft", "stole", "steal", "fraud"):
            self.assertNotIn(bad, text)

    def test_decisions_are_recorded_when_a_plan_is_clamped(self):
        plan = world.plan_group(4, "starter")
        self.assertIsInstance(plan.decisions, list)
        for d in plan.decisions:
            self.assertRegex(d, r"^c\d: ")


if __name__ == "__main__":
    unittest.main()

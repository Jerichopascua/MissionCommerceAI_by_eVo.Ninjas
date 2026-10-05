import unittest

from simpeso import behavior, runner, world

# a synthetic stand-in for a real product list: the repo never contains real products or prices
ITEMS = [{"code": f"B{i:04d}", "name": f"Item {i}", "cost": 10 + i % 20, "price": 12 + i % 20 + (i % 7), "sold_units": (30 if i < 3 else 0),
          "popularity": (8.2 if i < 3 else 0.2)} for i in range(60)]


class RealCatalogTests(unittest.TestCase):
    def test_every_company_and_branch_sells_the_given_catalog(self):
        plan = world.plan_group(21, "smoke", catalog=ITEMS)
        self.assertEqual(plan.settings["catalog_source"], "real")
        for c in plan.companies:
            self.assertEqual([p.code for p in c.catalog], [i["code"] for i in ITEMS])
            self.assertTrue(all(not p.expiry for p in c.catalog))

    def test_costs_and_prices_are_kept_exactly(self):
        plan = world.plan_group(21, "smoke", catalog=ITEMS)
        p = plan.companies[0].catalog[5]
        self.assertEqual((p.cost, p.price), (ITEMS[5]["cost"], ITEMS[5]["price"]))
        self.assertGreater(p.price, p.cost)

    def test_size_keeps_the_best_sellers_and_is_deterministic(self):
        a = world.real_specs(ITEMS, 10, seed=1)
        b = world.real_specs(ITEMS, 10, seed=1)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 10)
        self.assertTrue({"B0000", "B0001", "B0002"} <= {p.code for p in a})
        self.assertNotEqual([p.code for p in a], [p.code for p in world.real_specs(ITEMS, 10, seed=2)])

    def test_default_planning_is_unchanged_without_a_catalog(self):
        self.assertEqual(world.plan_hash(world.plan_group(21, "smoke")), world.plan_hash(world.plan_group(21, "smoke", catalog=None)))
        self.assertEqual(world.plan_group(21, "smoke").settings["catalog_source"], "generated")

    def test_best_sellers_dominate_the_baskets(self):
        plan = world.plan_group(21, "smoke", catalog=ITEMS)
        people = behavior.make_individuals(plan, 21)
        units = {}
        for d in range(1, 8):
            for v in behavior.day_visits(plan, people, d, 21):
                for code, q in v.lines:
                    units[code] = units.get(code, 0) + q
        top3 = sum(units.get(c, 0) for c in ("B0000", "B0001", "B0002")) / sum(units.values())
        self.assertGreater(top3, 0.15)               # 3 of 60 products (5%) carry well over their even share

    def test_purchase_lines_are_chunked_under_the_form_limit(self):
        lines = list(range(493))
        parts = list(runner.chunks(lines))
        self.assertEqual(sum(len(p) for p in parts), 493)
        self.assertTrue(all(len(p) <= runner.MAX_LINES_PER_PURCHASE for p in parts))
        self.assertLess(runner.MAX_LINES_PER_PURCHASE * 9, 1024)       # about 8 form values per line plus the header


if __name__ == "__main__":
    unittest.main()

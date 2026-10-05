import unittest

from simpeso import behavior, perishables as pr, world

# generic names only: no real business data in the repo
SHOULD = {"FRESH MILK 1L": "Chilled dairy", "YAKULT": "Chilled dairy", "YAKULT LIGHT": "Chilled dairy", "SOYMILK CHOCO 250ML": "Chilled dairy",
          "STAR MARGARINE REG 100G": "Chilled spreads and cheese", "PARMESAN CHEESE 85G": "Chilled spreads and cheese",
          "VIDA BACON 250G": "Chilled meat", "VIDA SWEET HAM 250G": "Chilled meat", "CRAZY CUT NUGGETS 200G": "Chilled meat",
          "CHICKEN TAPA 220G": "Chilled meat", "SALAD MACARONI": "Prepared salad", "SHIN KIMCHI 120G": "Chilled side dishes",
          "WHOOPIE MALLOW CAKE 10 X 34G": "Packaged cakes"}
SHOULD_NOT = ["SAMYANG BULDAK CHEESE 140G", "SURF LIQ. DET. ROSE FRESH 900ML", "ZONROX BLEACH LEMON 1000ML", "RELISH BREAD CRUMBS 60G",
              "SPAM LUNCHEON MEAT 12OZ", "CORNED BEEF 150G", "LIVER SPREAD 85G", "SOFY COOL FRESH 29CM", "TANG POWDER CALAMANSI 19G",
              "INSTANT NOODLES BEEF 55G", "SILKA SOAP SHEABUTTER 135G", "WAFER CHEESE 48G", "BIOGESIC", "SQUID FLAKES CRACKERS"]


class PerishableRuleTests(unittest.TestCase):
    def test_perishable_names_get_the_expected_class(self):
        for name, cat in SHOULD.items():
            rule = pr.classify(name)
            self.assertIsNotNone(rule, name)
            self.assertEqual(rule.category, cat, name)

    def test_shelf_stable_and_non_food_names_never_match(self):
        for name in SHOULD_NOT:
            self.assertIsNone(pr.classify(name), name)

    def test_shelf_life_ranges_are_sane_and_alert_days_are_bounded(self):
        for rule in pr.RULES:
            lo, hi = rule.shelf_life_days
            self.assertTrue(0 < lo < hi <= 365)
            self.assertTrue(2 <= pr.alert_days(rule.shelf_life_days) <= 30)
        self.assertEqual(pr.alert_days((3, 7)), 2)
        self.assertEqual(pr.alert_days((60, 120)), 20)

    def test_matching_is_case_insensitive(self):
        self.assertIsNotNone(pr.classify("fresh milk 1l"))


ITEMS = [{"code": f"P{i:03d}", "name": n, "cost": 20 + i, "price": 26 + i, "sold_units": 0, "popularity": 0.2}
         for i, n in enumerate(list(SHOULD) + SHOULD_NOT)]


class PerishableCatalogTests(unittest.TestCase):
    def test_default_stays_non_expiry(self):
        specs = world.real_specs(ITEMS)
        self.assertTrue(all(not s.expiry for s in specs))

    def test_perishables_flag_marks_only_matching_products_and_keeps_real_prices(self):
        specs = {s.name: s for s in world.real_specs(ITEMS, perishables=True)}
        for name in SHOULD:
            s = specs[name]
            self.assertTrue(s.expiry and s.shelf_life_days and s.alert_days >= 2, name)
        for name in SHOULD_NOT:
            self.assertFalse(specs[name].expiry, name)
        src = {i["name"]: i for i in ITEMS}
        for name, s in specs.items():
            self.assertEqual((s.cost, s.price), (src[name]["cost"], src[name]["price"]))

    def test_popularity_never_drops_below_the_class_floor(self):
        s = {x.name: x for x in world.real_specs(ITEMS, perishables=True)}["FRESH MILK 1L"]
        self.assertGreaterEqual(s.popularity, 2.0)

    def test_plan_marks_every_company_and_perishable_baskets_can_happen(self):
        plan = world.plan_group(21, "smoke", catalog=ITEMS, perishables=True)
        self.assertTrue(plan.settings["real_perishables"])
        for c in plan.companies:
            self.assertEqual(sum(1 for p in c.catalog if p.expiry), len(SHOULD))
        people = behavior.make_individuals(plan, 21)
        perishable_codes = {p.code for p in plan.companies[0].catalog if p.expiry}
        bought = {code for d in range(1, 8) for v in behavior.day_visits(plan, people, d, 21) for code, _ in v.lines}
        self.assertTrue(bought & perishable_codes)


if __name__ == "__main__":
    unittest.main()

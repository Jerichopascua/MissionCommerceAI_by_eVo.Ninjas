import unittest
from dataclasses import replace
from simpeso import rng, verticals


class RngTests(unittest.TestCase):
    def test_same_inputs_same_stream(self):
        self.assertEqual(rng.derive(7, "x", 1).random(), rng.derive(7, "x", 1).random())

    def test_keys_are_independent(self):
        self.assertNotEqual(rng.derive(7, "x").random(), rng.derive(7, "y").random())
        self.assertNotEqual(rng.derive(7, "x").random(), rng.derive(8, "x").random())

    def test_stable_hash_ignores_key_order(self):
        self.assertEqual(rng.stable_hash({"a": 1, "b": 2}), rng.stable_hash({"b": 2, "a": 1}))


class VerticalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = verticals.load_all()

    def test_five_templates_all_valid(self):
        self.assertEqual(set(self.all), {"convenience", "grocery_pharmacy", "motorcycle_parts", "mixed", "sports"})
        for v in self.all.values():
            self.assertEqual(verticals.validate(v), [], v.name)

    def test_bad_margin_band_is_rejected(self):
        v = replace(self.all["convenience"], margin_band=(0.5, 0.2))
        self.assertTrue(any("margin band" in p for p in verticals.validate(v)))

    def test_expiry_category_needs_shelf_life(self):
        cats = list(self.all["convenience"].categories)
        cats[0] = replace(cats[0], shelf_life_days=())
        v = replace(self.all["convenience"], categories=tuple(cats))
        self.assertTrue(any("shelf_life_days" in p for p in verticals.validate(v)))

    def test_empty_categories_rejected(self):
        v = replace(self.all["sports"], categories=())
        self.assertTrue(any("no categories" in p for p in verticals.validate(v)))

    def test_catalog_deterministic_and_within_band(self):
        for v in self.all.values():
            a = verticals.build_catalog(v, rng.derive(3, v.name), 30)
            b = verticals.build_catalog(v, rng.derive(3, v.name), 30)
            self.assertEqual(a, b)
            self.assertEqual(len(a), 30)
            self.assertEqual(len({p.code for p in a}), 30)
            for p in a:
                m = verticals.margin_of(p.cost, p.price)
                self.assertGreaterEqual(m, v.margin_band[0] - 1e-9, p)
                self.assertLessEqual(m, v.margin_band[1] + 1e-9, p)
                self.assertEqual(bool(p.expiry), bool(p.shelf_life_days))

    def test_expiry_only_in_expiry_verticals(self):
        moto = verticals.build_catalog(self.all["motorcycle_parts"], rng.derive(1), 40)
        self.assertFalse(any(p.expiry for p in moto))
        conv = verticals.build_catalog(self.all["convenience"], rng.derive(1), 40)
        self.assertTrue(all(p.expiry and p.alert_days >= 1 for p in conv))


if __name__ == "__main__":
    unittest.main()

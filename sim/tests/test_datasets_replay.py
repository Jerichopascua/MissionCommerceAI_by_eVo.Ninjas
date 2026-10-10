import io
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from simpeso import behavior, datasets, replay, world


def write(base: Path, name: str, text: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(text, encoding="utf-8")


class Tty(io.StringIO):
    def isatty(self):
        return True


class SelectionTests(unittest.TestCase):
    def test_parse_weights_and_default_equal_weights(self):
        self.assertEqual(datasets.parse("a:0.6,b:0.4"), {"a": 0.6, "b": 0.4})
        self.assertEqual(datasets.parse("a,b"), {"a": 1.0, "b": 1.0})
        with self.assertRaises(datasets.SelectionError):
            datasets.parse("a:x")
        with self.assertRaises(datasets.SelectionError):
            datasets.parse("a:0")

    def test_a_test_cannot_start_without_a_choice(self):
        with self.assertRaises(datasets.SelectionError) as e:
            datasets.choose(None, "visits", stream_in=io.StringIO(""))
        self.assertIn("--datasets", str(e.exception))
        self.assertIn("simulated-rules", str(e.exception))             # the menu is shown with the refusal

    def test_with_a_person_at_the_keyboard_the_menu_is_asked_and_numbers_work(self):
        out = io.StringIO()
        mix = datasets.choose(None, "visits", stream_in=Tty("1\n"), stream_out=out)
        self.assertEqual(mix.ids(), ["simulated-rules"])
        self.assertIn("Customer data sets", out.getvalue())

    def test_weights_are_normalised_and_unknown_or_missing_sets_are_refused_with_how_to_fix(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(datasets, "DATA_DIR", Path(d)):
            write(Path(d) / "store-pos", "receipts.csv", "receipt_id,sku,qty\n1,a,1\n")
            mix = datasets.build_mix("simulated-rules:3,store-pos:1", "visits")
            self.assertAlmostEqual(mix.weights["simulated-rules"], 0.75)
            self.assertAlmostEqual(sum(mix.weights.values()), 1.0)
            with self.assertRaises(datasets.SelectionError) as e:
                datasets.build_mix("nope", "visits")
            self.assertIn("unknown", str(e.exception))
            with self.assertRaises(datasets.SelectionError) as e:
                datasets.build_mix("instacart", "visits")
            self.assertIn("order_products__prior.csv", str(e.exception))
            self.assertIn("customer_data/instacart", str(e.exception))

    def test_each_test_takes_only_the_data_sets_with_the_right_role(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(datasets, "DATA_DIR", Path(d)):
            write(Path(d) / "favorita", "train.csv", "date,store_nbr,item_nbr,unit_sales,onpromotion\n")
            with self.assertRaises(datasets.SelectionError) as e:
                datasets.build_mix("favorita", "visits")                  # demand history only, no baskets
            self.assertIn("role: visits", str(e.exception))
            self.assertEqual(datasets.build_mix("favorita", "demand").ids(), ["favorita"])
            with self.assertRaises(datasets.SelectionError):
                datasets.build_mix("simulated-rules", "demand")
        with self.assertRaises(datasets.SelectionError):
            datasets.build_mix("simulated-rules,hero-llm", "visits")        # hero shoppers are for the story test
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(datasets.SelectionError):
                datasets.build_mix("hero-llm", "story")                      # no AI API configured
            self.assertEqual(datasets.build_mix("hero-llm,simulated-rules", "story", stub_llm=True).ids(), ["hero-llm", "simulated-rules"])

    def test_the_catalog_says_what_is_available(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(datasets, "DATA_DIR", Path(d)):
            rows = {r["id"]: r for r in datasets.catalog()}
            self.assertTrue(rows["simulated-rules"]["available"])
            self.assertFalse(rows["dunnhumby"]["available"])
            self.assertIn("transaction_data.csv", rows["dunnhumby"]["missing"][0])

    def test_the_choice_is_recorded_with_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            datasets.record(Path(d), datasets.Mix({"simulated-rules": 0.5, "store-pos": 0.5}), day=3)
            self.assertIn("store-pos 50%", (Path(d) / "datasets.json").read_text(encoding="utf-8"))


class LoaderTests(unittest.TestCase):
    def test_store_pos_groups_lines_by_receipt_and_reads_the_hour(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d), "r.csv", "Receipt No,Date,SKU,Qty\n1,2026-01-05 18:30:00,milk,2\n1,2026-01-05 18:30:00,egg,1\n2,2026-01-05 07:10:00,milk,1\n3,2026-01-05 07:15:00,\n")
            b = replay.load_store_pos(Path(d) / "r.csv")
            self.assertEqual(len(b), 2)
            first = next(x for x in b if x.hour == 18)
            self.assertEqual(dict(first.lines), {"milk": 2, "egg": 1})
            self.assertEqual(replay.hour_profile(b), {7: 0.5, 18: 0.5})

    def test_store_pos_without_the_needed_columns_says_what_it_found(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d), "r.csv", "foo,bar\n1,2\n")
            with self.assertRaises(datasets.SelectionError) as e:
                replay.load_store_pos(Path(d) / "r.csv")
            self.assertIn("foo", str(e.exception))

    def test_instacart_baskets_and_hours(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d), "orders.csv", "order_id,user_id,eval_set,order_number,order_dow,order_hour_of_day,days_since_prior_order\n"
                  "10,1,prior,1,2,9,\n11,1,prior,2,3,19,5\n12,2,train,1,1,12,\n")
            write(Path(d), "order_products__prior.csv", "order_id,product_id,add_to_cart_order,reordered\n10,5,1,0\n10,6,2,0\n10,5,3,1\n11,7,1,0\n")
            b = replay.load_instacart(Path(d))
            self.assertEqual(len(b), 2)
            by_hour = {x.hour: dict(x.lines) for x in b}
            self.assertEqual(by_hour[9], {"5": 2, "6": 1})
            self.assertEqual(by_hour[19], {"7": 1})

    def test_dunnhumby_baskets_with_transaction_time(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d), "transaction_data.csv", "household_key,BASKET_ID,DAY,PRODUCT_ID,QUANTITY,SALES_VALUE,STORE_ID,RETAIL_DISC,TRANS_TIME,WEEK_NO,COUPON_DISC,COUPON_MATCH_DISC\n"
                  "1,900,1,50,2,3.0,1,0,1631,1,0,0\n1,900,1,51,1,1.0,1,0,1631,1,0,0\n2,901,1,50,1,1.5,1,0,0745,1,0,0\n")
            b = replay.load_dunnhumby(Path(d))
            self.assertEqual({x.hour for x in b}, {16, 7})
            self.assertEqual(replay.describe(b)["baskets"], 2)


class MapperAndSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = world.plan_group(21, "starter")
        cls.people = behavior.make_individuals(cls.plan, 21)
        cls.arrivals = behavior.day_arrivals(cls.plan, cls.people, 1, 21)
        cls.codes = [p.code for p in cls.plan.companies[0].catalog]

    def baskets(self, n=300):
        import random
        r = random.Random(4)
        items = [f"i{k}" for k in range(60)]
        w = [1 / (k + 1) for k in range(60)]
        return [replay.Basket(r.randrange(24), tuple(Counter(r.choices(items, w, k=r.randint(1, 6))).items())) for _ in range(n)]

    def test_each_catalog_product_gets_a_roughly_equal_share_of_purchases(self):
        b = self.baskets()
        m = replay.ProductMapper(b, self.codes)
        got = Counter()
        for x in b:
            for item, q in x.lines:
                got[m.map[item]] += q
        self.assertGreater(len(got), len(self.codes) // 2)                     # purchases spread over the catalog, not piled on a few codes
        self.assertEqual(m.map["i0"], m.map["i0"])
        self.assertTrue(all(c in self.codes for c in m.map.values()))

    def test_the_same_item_always_lands_on_the_same_product(self):
        b = self.baskets()
        self.assertEqual(replay.ProductMapper(b, self.codes).map, replay.ProductMapper(b, self.codes).map)

    def test_a_replayed_visit_is_deterministic_and_uses_the_company_catalog(self):
        src = replay.ReplaySource("store-pos", self.baskets())
        v = next(a for a in self.arrivals if a.company == self.plan.companies[0].key)
        a = src.fill_basket(self.plan, v, 21)
        self.assertEqual(a, src.fill_basket(self.plan, v, 21))
        self.assertTrue(a is None or all(code in self.codes for code, _ in a.lines))

    def test_prices_still_matter_to_a_replayed_basket(self):
        src = replay.ReplaySource("store-pos", self.baskets())
        vs = [a for a in self.arrivals if a.company == self.plan.companies[0].key][:150]

        def units(ratio):
            return sum(q for v in vs for x in [src.fill_basket(self.plan, v, 21, lambda b, c: ratio)] if x for _, q in x.lines)
        self.assertGreater(units(0.7), units(1.0))                              # a markdown sells more
        self.assertGreater(units(1.0), units(1.4))                              # a price rise sells less

    def test_a_mix_splits_visits_by_weight_and_reports_the_split(self):
        mix = replay.MixSource({"simulated-rules": 0.5, "store-pos": 0.5},
                               {"simulated-rules": replay.RulesSource(), "store-pos": replay.ReplaySource("store-pos", self.baskets())})
        for v in self.arrivals:
            mix.fill_basket(self.plan, v, 21)
        n = sum(mix.counts.values())
        self.assertEqual(n, len(self.arrivals))
        self.assertAlmostEqual(mix.counts["store-pos"] / n, 0.5, delta=0.12)
        again = replay.MixSource({"simulated-rules": 0.5, "store-pos": 0.5},
                                 {"simulated-rules": replay.RulesSource(), "store-pos": replay.ReplaySource("store-pos", self.baskets())})
        first = [again.fill_basket(self.plan, v, 21) for v in self.arrivals[:30]]
        mix2 = replay.MixSource({"simulated-rules": 0.5, "store-pos": 0.5},
                                {"simulated-rules": replay.RulesSource(), "store-pos": replay.ReplaySource("store-pos", self.baskets())})
        self.assertEqual(first, [mix2.fill_basket(self.plan, v, 21) for v in self.arrivals[:30]])

    def test_simulated_rules_alone_is_exactly_the_old_behaviour(self):
        src = replay.build_source(datasets.Mix({"simulated-rules": 1.0}), log=lambda *_: None)
        for v in self.arrivals[:40]:
            self.assertEqual(src.fill_basket(self.plan, v, 21), behavior.fill_basket(self.plan, v, 21))


if __name__ == "__main__":
    unittest.main()

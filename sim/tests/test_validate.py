import csv
import io
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simpeso import datasets, validate


def synthetic(key="p", days=120, beta=-2.0, base=40.0, spread=0.25, seed=1, category="all"):
    """Units follow base * (price / 100) ** beta with Poisson-like noise; the price wanders by +/- spread every day."""
    r = random.Random(seed)
    price, units = [], []
    for _ in range(days):
        p = 100 * (1 + r.uniform(-spread, spread))
        mu = base * (p / 100) ** beta
        u = max(0.0, r.gauss(mu, math.sqrt(mu)))
        price.append(p)
        units.append(round(u))
    return validate.Series(key, category, list(range(days)), price, units)


class BacktestTests(unittest.TestCase):
    def test_price_awareness_wins_when_price_really_moves_demand(self):
        series = [synthetic(f"p{i}", seed=i) for i in range(12)]
        r = validate.backtest_price_model(series)
        self.assertEqual(r["series_used"], 12)
        self.assertGreater(r["days_with_price_move"], 100)
        moved = r["wape_price_move_days"]
        self.assertLess(moved["price_aware"], moved["average"])
        self.assertLess(moved["price_aware"], moved["recent_average"])
        self.assertIn("beat every price-blind baseline", r["verdict"])
        gain = r["price_awareness_gain_on_price_move_days"]
        self.assertGreater(gain["fixed_level_vs_average"], 0.05)           # like for like, price awareness lowers the error
        self.assertGreater(gain["recent_level_vs_recent_average"], 0.05)
        self.assertLess(r["betas"]["all"], -1.0)                       # it found that a higher price sells fewer

    def test_the_report_says_so_when_price_awareness_does_not_help(self):
        series = [synthetic(f"p{i}", beta=0.0, seed=i) for i in range(12)]       # price makes no difference to units
        r = validate.backtest_price_model(series)
        self.assertEqual(r["series_used"], 12)
        self.assertIn("did NOT clearly beat", r["verdict"])

    def test_products_without_price_variation_or_enough_days_are_left_out(self):
        flat = validate.Series("flat", "all", list(range(120)), [100.0] * 120, [10.0] * 120)
        short = synthetic("short", days=20)
        r = validate.backtest_price_model([flat, short])
        self.assertEqual(r["series_used"], 0)
        self.assertIn("enough price variation", r["note"])

    def test_it_never_trains_on_the_days_it_is_tested_on(self):
        s = synthetic("p", days=100)
        poisoned = validate.Series(s.key, s.category, s.days, s.price, s.units[:70] + [10 ** 6] * 30)        # an absurd test period
        clean = validate.backtest_price_model([s])
        dirty = validate.backtest_price_model([poisoned])
        self.assertEqual(clean["betas"], dirty["betas"])                                                     # the fit saw only the first 70 days


class LoaderTests(unittest.TestCase):
    def test_store_pos_series_need_a_price_column_and_build_daily_series(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.csv"
            rows = ["receipt_id,date,sku,qty,price,category"]
            for day in range(60):
                price = 20 if day % 3 else 15
                rows.append(f"{day},2026-01-{1 + day % 28:02d},A,{3 if price == 15 else 2},{price},Snacks")
            path.write_text("\n".join(rows), encoding="utf-8")
            with self.assertRaises(datasets.SelectionError):
                path.write_text("receipt_id,date,sku,qty\n1,2026-01-01,A,1\n", encoding="utf-8")
                validate.series_from_store_pos(path)

    def test_dunnhumby_series_are_daily_units_and_average_price(self):
        with tempfile.TemporaryDirectory() as d:
            rows = ["household_key,BASKET_ID,DAY,PRODUCT_ID,QUANTITY,SALES_VALUE,STORE_ID,RETAIL_DISC,TRANS_TIME,WEEK_NO,COUPON_DISC,COUPON_MATCH_DISC"]
            for day in range(1, 241):
                price = 2.0 if day % 4 else 1.5
                for h in range(3):
                    rows.append(f"{h},{day * 10 + h},{day},777,2,{2 * price},1,0,1200,1,0,0")
            (Path(d) / "transaction_data.csv").write_text("\n".join(rows), encoding="utf-8")
            s = validate.series_from_dunnhumby(Path(d), top=5)
            self.assertEqual(len(s), 1)
            self.assertEqual(len(s[0].days), 240)
            self.assertEqual(s[0].units[0], 6.0)
            self.assertEqual(sorted(set(s[0].price)), [1.5, 2.0])


class MissionValidationTests(unittest.TestCase):
    def test_answers_are_matched_to_receipts_and_scored(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(datasets, "DATA_DIR", Path(d)):
            rec = ["receipt_id,datetime,sku,qty,price"]
            ans = ["receipt_id,mission"]
            for i in range(20):                                           # 20 one-item morning baskets, answered "Morning grab-and-go"
                rec.append(f"m{i},2026-01-05 07:30:00,milk,1,50")
                ans.append(f"m{i},Morning grab-and-go")
            for i in range(10):                                           # 10 big baskets, answered "Weekly restock"
                for k in range(9):
                    rec.append(f"w{i},2026-01-04 11:00:00,item{k},1,40")
                ans.append(f"w{i},weekly_restock")
            for i in range(5):                                            # 5 evening 3-line baskets the shopper called a dinner run
                for k in range(3):
                    rec.append(f"d{i},2026-01-05 18:30:00,food{k},1,20")
                ans.append(f"d{i},Dinner run")
            base = Path(d)
            (base / "store-pos").mkdir()
            (base / "till-survey").mkdir()
            (base / "store-pos" / "receipts.csv").write_text("\n".join(rec), encoding="utf-8")
            (base / "till-survey" / "answers.csv").write_text("\n".join(ans), encoding="utf-8")
            r = validate.validate_missions()
            self.assertEqual(r["baskets_matched"], 35)
            self.assertEqual(r["confusion"]["Morning grab-and-go"], {"Morning grab-and-go": 20})
            self.assertEqual(r["confusion"]["Weekly restock"], {"Weekly restock": 10})
            self.assertEqual(r["confusion"]["Dinner run"], {"After-work top-up": 5})      # perishables are not visible in this file
            self.assertAlmostEqual(r["agreement"], 30 / 35, places=3)
            self.assertEqual(r["commonest_answer"], "Morning grab-and-go")

    def test_unmatched_or_unreadable_answers_are_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(datasets, "DATA_DIR", Path(d)):
            base = Path(d)
            (base / "store-pos").mkdir()
            (base / "till-survey").mkdir()
            (base / "store-pos" / "receipts.csv").write_text("receipt_id,datetime,sku,qty\nx,2026-01-05 07:30:00,a,1\n", encoding="utf-8")
            (base / "till-survey" / "answers.csv").write_text("receipt_id,mission\nnope,Quick top-up\nx,I was bored\n", encoding="utf-8")
            r = validate.validate_missions()
            self.assertEqual(r["baskets_matched"], 0)
            self.assertIn("no answer could be matched", r["note"])


if __name__ == "__main__":
    unittest.main()

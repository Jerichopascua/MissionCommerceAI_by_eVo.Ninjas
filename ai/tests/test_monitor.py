import datetime as dt
import unittest

from missionai import monitor as m

TODAY = dt.date(2026, 10, 20)
NAMES = {1: "Main"}


def days(values, end=TODAY - dt.timedelta(days=1)):
    n = len(values)
    return {end - dt.timedelta(days=n - 1 - i): v for i, v in enumerate(values)}


class SalesTests(unittest.TestCase):
    def test_a_halved_day_is_flagged_with_the_comparison(self):
        out = m.sales_findings({1: days([1000, 1100, 950, 1050, 1000, 1020, 980, 1010, 400])}, NAMES, TODAY)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "Sales")
        self.assertIn("below its usual", out[0]["message"])
        self.assertTrue(out[0]["key"].startswith("sales-drop:1:"))

    def test_an_ordinary_day_is_not_flagged(self):
        self.assertEqual(m.sales_findings({1: days([1000, 1100, 950, 1050, 1000, 1020, 980, 1010, 900])}, NAMES, TODAY), [])

    def test_a_spike_is_flagged_but_worded_as_worth_knowing(self):
        out = m.sales_findings({1: days([1000, 1100, 950, 1050, 1000, 1020, 980, 1010, 2600])}, NAMES, TODAY)
        self.assertEqual(out[0]["key"].split(":")[0], "sales-spike")
        self.assertIn("Worth knowing why", out[0]["message"])

    def test_too_little_history_says_nothing(self):
        self.assertEqual(m.sales_findings({1: days([1000, 1000, 1000, 100])}, NAMES, TODAY), [])

    def test_today_is_never_judged_it_is_not_finished(self):
        d = days([1000, 1100, 950, 1050, 1000, 1020, 980, 1010])
        d[TODAY] = 10
        self.assertEqual(m.sales_findings({1: d}, NAMES, TODAY), [])

    def test_a_naturally_noisy_branch_is_not_flagged_for_a_normal_dip(self):
        out = m.sales_findings({1: days([500, 1500, 700, 1400, 600, 1300, 800, 1200, 520])}, NAMES, TODAY)
        self.assertEqual(out, [])

    def test_daily_totals_groups_by_date(self):
        t = m.daily_totals([{"saleDate": "2026-10-19T09:00:00", "totalAmount": 10}, {"saleDate": "2026-10-19T17:30:00", "totalAmount": 5.5}, {"saleDate": "2026-10-18T10:00:00", "totalAmount": 1}])
        self.assertEqual(t[dt.date(2026, 10, 19)], 15.5)
        self.assertEqual(len(t), 2)


def shift(i, cashier, variance, wh=1):
    return {"id": i, "warehouseId": wh, "cashierId": cashier, "variance": variance, "closedAt": f"2026-10-{10 + i // 3:02d}T20:00:{i % 60:02d}"}


class CashTests(unittest.TestCase):
    def test_one_big_difference_stands_out_against_the_usual(self):
        rows = [shift(i, 7, v) for i, v in enumerate([0, -5, 3, 0, -2, 4, 0, -250], start=1)]
        out = m.cash_findings(rows, NAMES)
        self.assertTrue(any(f["key"].startswith("cash-big:") and f["value"] == 250 for f in out))

    def test_a_small_difference_is_never_flagged_alone(self):
        rows = [shift(i, 7, v) for i, v in enumerate([0, 0, 0, 0, 0, 0, 0, -40], start=1)]
        self.assertEqual(m.cash_findings(rows, NAMES), [])

    def test_a_cashier_short_again_and_again_is_flagged_without_an_accusation(self):
        rows = [shift(i, 7 if i % 2 else 8, v) for i, v in enumerate([0, -30, 0, -25, 0, -40, 0, -35, 0, -50], start=1)]
        out = m.cash_findings(rows, NAMES, {8: "Ana"})
        rep = [f for f in out if f["key"].startswith("cash-repeat")]
        self.assertEqual(len(rep), 1)
        self.assertIn("Ana", rep[0]["message"])
        self.assertIn("worth a look together", rep[0]["message"])

    def test_nothing_with_few_shifts_for_the_big_check(self):
        self.assertEqual(m.cash_findings([shift(1, 7, -500), shift(2, 7, 0)], NAMES), [])

    def test_open_shifts_without_variance_are_ignored(self):
        self.assertEqual(m.cash_findings([{"id": 1, "warehouseId": 1, "cashierId": 7, "variance": None, "closedAt": None}], NAMES), [])


def ev(kind, day, wh=1):
    return {"eventType": kind, "warehouseId": wh, "occurredAt": f"{day.isoformat()}T10:00:00"}


class ReturnsTests(unittest.TestCase):
    def test_a_burst_of_returns_today_against_a_quiet_past_is_flagged(self):
        past = [ev("SaleCompleted", TODAY - dt.timedelta(days=2))] * 60 + [ev("SaleReturned", TODAY - dt.timedelta(days=2))] * 1
        now = [ev("SaleCompleted", TODAY)] * 20 + [ev("SaleReturned", TODAY)] * 3 + [ev("SaleDeleted", TODAY)] * 2
        out = m.returns_findings(past + now, NAMES, TODAY)
        self.assertEqual(len(out), 1)
        self.assertIn("5 sales were returned or deleted against 20", out[0]["message"])

    def test_a_branch_that_always_has_returns_is_not_flagged(self):
        past = [ev("SaleCompleted", TODAY - dt.timedelta(days=2))] * 30 + [ev("SaleReturned", TODAY - dt.timedelta(days=2))] * 5
        now = [ev("SaleCompleted", TODAY)] * 30 + [ev("SaleReturned", TODAY)] * 5
        self.assertEqual(m.returns_findings(past + now, NAMES, TODAY), [])

    def test_two_events_are_too_few(self):
        now = [ev("SaleCompleted", TODAY)] * 5 + [ev("SaleDeleted", TODAY)] * 2
        self.assertEqual(m.returns_findings(now, NAMES, TODAY), [])


class LedgerAndAllTests(unittest.TestCase):
    def test_drift_is_one_finding_per_branch_naming_the_largest(self):
        rows = [{"warehouseId": 1, "productId": 5, "drift": -2}, {"warehouseId": 1, "productId": 6, "drift": 7}, {"warehouseId": 1, "productId": 9, "drift": 0}]
        out = m.ledger_findings(rows, NAMES)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 2.0)
        self.assertIn("product 6", out[0]["message"])

    def test_no_drift_no_finding(self):
        self.assertEqual(m.ledger_findings([{"warehouseId": 1, "productId": 5, "drift": 0}], NAMES), [])

    def test_all_findings_keys_are_unique_and_stable(self):
        kwargs = dict(names=NAMES, today=TODAY, daily_sales={1: days([1000, 1100, 950, 1050, 1000, 1020, 980, 1010, 400])},
                      drift=[{"warehouseId": 1, "productId": 5, "drift": -2}])
        a, b = m.all_findings(**kwargs), m.all_findings(**kwargs)
        self.assertEqual([f["key"] for f in a], [f["key"] for f in b])
        self.assertEqual(len({f["key"] for f in a}), len(a))
        self.assertEqual(len(a), 2)


if __name__ == "__main__":
    unittest.main()

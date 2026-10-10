import datetime as dt
import io
import os
import unittest
from contextlib import redirect_stderr
from unittest import mock

from simpeso import agent_service


class Acct:
    token = "t"


class FakeDrv:
    """movements(acct, wh, kind, after_id, since) like PesoWebDriver.movements: pages of at most 5000 rows with increasing ids."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def movements(self, acct, wh, kind="SALE_OUT", after_id=0, since=None):
        self.calls.append((wh, after_id, since))
        out = [r for r in self.rows if r["warehouseId"] == wh and r["id"] > after_id and (since is None or r["transactionDate"][:10] >= since)]
        return sorted(out, key=lambda r: r["id"])[:agent_service.SALES_PAGE]


def row(i, wh, pid, qty, day):
    return {"id": i, "warehouseId": wh, "productId": pid, "qtyOut": qty, "transactionDate": f"{day}T10:00:00"}


END = dt.date(2026, 10, 10)


class ModelFromSalesTests(unittest.TestCase):
    def test_rate_is_units_per_day_over_the_days_since_the_branch_first_sold(self):
        rows = [row(1, 1, 7, 10, "2026-10-01"), row(2, 1, 7, 10, "2026-10-05"), row(3, 1, 8, 4, "2026-10-09")]       # first sale 10 days before the end
        m = agent_service.model_from_sales(FakeDrv(rows), Acct(), [1], window_days=28, as_of=END)
        self.assertAlmostEqual(m["rates"]["1:7"], 2.0)             # 20 units over 10 days
        self.assertAlmostEqual(m["rates"]["1:8"], 0.4)
        self.assertEqual(m["window"]["span_by_branch"][1], 10)
        self.assertEqual(m["observations"], {})                    # price sensitivity is not learned for a real company yet: it will say assumed

    def test_the_window_cuts_old_sales_and_a_young_branch_gets_a_floor_on_its_span(self):
        rows = [row(1, 1, 7, 100, "2026-08-01"), row(2, 1, 7, 6, "2026-10-10")]
        m = agent_service.model_from_sales(FakeDrv(rows), Acct(), [1], window_days=28, as_of=END)
        self.assertAlmostEqual(m["rates"]["1:7"], 6 / agent_service.MIN_SPAN_DAYS)             # the old sale is outside the window; one day of data is not divided by 1

    def test_as_of_lets_a_company_whose_last_sales_are_older_be_looked_at(self):
        rows = [row(1, 1, 7, 14, "2026-05-20"), row(2, 1, 7, 14, "2026-05-30")]
        today = agent_service.model_from_sales(FakeDrv(rows), Acct(), [1], 28, None)
        self.assertEqual(today["rates"], {})
        then = agent_service.model_from_sales(FakeDrv(rows), Acct(), [1], 28, dt.date(2026, 5, 30))
        self.assertAlmostEqual(then["rates"]["1:7"], 28 / 11)
        after = agent_service.model_from_sales(FakeDrv(rows + [row(3, 1, 7, 99, "2026-06-15")]), Acct(), [1], 28, dt.date(2026, 5, 30))
        self.assertAlmostEqual(after["rates"]["1:7"], 28 / 11)                                 # sales after the as-of day are not counted

    def test_every_page_of_sales_is_read(self):
        n = agent_service.SALES_PAGE + 10
        rows = [row(i, 1, 7, 1, "2026-10-09") for i in range(1, n + 1)]
        drv = FakeDrv(rows)
        m = agent_service.model_from_sales(drv, Acct(), [1], 28, END)
        self.assertEqual(len(drv.calls), 2)
        self.assertAlmostEqual(m["rates"]["1:7"], n / 3)                                       # two days of data is floored to 3

    def test_each_branch_gets_its_own_rates(self):
        rows = [row(1, 1, 7, 5, "2026-10-08"), row(2, 2, 7, 9, "2026-10-08")]
        m = agent_service.model_from_sales(FakeDrv(rows), Acct(), [1, 2], 28, END)
        self.assertIn("1:7", m["rates"])
        self.assertIn("2:7", m["rates"])
        self.assertNotEqual(m["rates"]["1:7"], m["rates"]["2:7"])


class ServeRealTests(unittest.TestCase):
    def test_it_needs_an_email_and_a_password_and_never_asks_a_non_terminal(self):
        class Args:
            email = None
            base_url = "http://x"
            history_days = 28
            as_of = None
            limit = 8
            once = True
            interval = 30.0
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(agent_service.serve_real(Args()), 2)
        self.assertIn("--email", err.getvalue())
        Args.email = "owner@shop.test"
        not_a_terminal = mock.Mock()
        not_a_terminal.isatty.return_value = False
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("sys.stdin", not_a_terminal), redirect_stderr(err):
            self.assertEqual(agent_service.serve_real(Args()), 2)
        self.assertIn("PESOWEB_AGENT_PASSWORD", err.getvalue())

    def test_the_pricing_handler_rebuilds_a_real_companys_model_on_every_run(self):
        calls = []

        def model():
            calls.append(1)
            return {"rates": {}, "observations": {}, "estimates": {}}
        with mock.patch("simpeso.price_run.suggestions_for", return_value=([], [], {})) as sugg, \
                mock.patch("simpeso.price_run.propose_top", return_value=[]):
            run = agent_service.pricing_handler(object(), Acct(), [1], model)
            run()
            run()
        self.assertEqual(len(calls), 2)
        self.assertEqual(sugg.call_count, 2)


if __name__ == "__main__":
    unittest.main()

import datetime as dt
import unittest

from simpeso import agent_service


class Acct:
    token = "t"


class FakeDriver:
    def __init__(self, status=200):
        self.status, self.posted, self.calls = status, [], []

    def _call(self, method, path, token=None, **kw):
        self.calls.append((method, path))
        return {}

    def branch_names(self, acct):
        return {1: "Main"}

    def baskets(self, acct, wh, after, since):
        days = [1000, 1100, 950, 1050, 1000, 1020, 980, 1010, 300]
        end = dt.date(2026, 10, 19)
        return {"baskets": [{"saleDate": f"{(end - dt.timedelta(days=len(days) - 1 - i)).isoformat()}T12:00:00", "totalAmount": v} for i, v in enumerate(days)]}

    def events(self, acct, after=0, take=1000):
        return {"events": [], "nextAfterId": after}

    def cash_shifts(self, acct):
        return []

    def ledger_drift(self, acct):
        return [{"warehouseId": 1, "productId": 4, "drift": -3}]

    def post_monitor_findings(self, acct, findings):
        self.posted.append(findings)
        return self.status, {"opened": len(findings), "updated": 0, "closed": 0}


class MonitoringHandlerTests(unittest.TestCase):
    def test_it_checks_the_rules_then_posts_what_is_unusual(self):
        d = FakeDriver()
        summary = agent_service.monitoring_handler(d, Acct(), [1], today=dt.date(2026, 10, 20))()
        self.assertIn(("POST", "/api/ai/hub/evaluate"), d.calls)
        kinds = sorted(f["kind"] for f in d.posted[0])
        self.assertEqual(kinds, ["Ledger", "Sales"])
        self.assertIn("2 unusual", summary)
        self.assertIn("2 new", summary)

    def test_a_clean_scan_still_posts_so_old_findings_close(self):
        d = FakeDriver()
        d.ledger_drift = lambda acct: []
        d.baskets = lambda acct, wh, after, since: {"baskets": []}
        summary = agent_service.monitoring_handler(d, Acct(), [1], today=dt.date(2026, 10, 20))()
        self.assertEqual(d.posted, [[]])
        self.assertIn("nothing unusual", summary)

    def test_a_refusal_fails_the_run_with_the_reason(self):
        with self.assertRaises(RuntimeError):
            agent_service.monitoring_handler(FakeDriver(status=422), Acct(), [1], today=dt.date(2026, 10, 20))()


if __name__ == "__main__":
    unittest.main()

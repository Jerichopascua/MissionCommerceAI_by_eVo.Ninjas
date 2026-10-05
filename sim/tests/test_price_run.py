import unittest
from types import SimpleNamespace

from simpeso import price_run


def sugg(pid, gain, status="raise", price=100.0, to=105.0):
    return SimpleNamespace(product_id=pid, name=f"P{pid}", price=price, suggested_price=to, status=status, profit_gain_per_day=gain,
                           profit_gain_if_more_sensitive=gain / 2, beta=-1.3, beta_source="assumed", reason="r", floor_price=to, cost=90.0)


class FakeDriver:
    def __init__(self, pending=()):
        self.pending, self.sent = list(pending), []

    def list_price_changes(self, acct, status=None, product_id=None):
        return [{"productId": p} for p in self.pending]

    def propose_list_price(self, acct, wh, pid, price, **kw):
        self.sent.append((pid, kw))
        return 202, {}


class ProposeTopTests(unittest.TestCase):
    def test_takes_the_largest_gains_first_up_to_the_limit(self):
        drv = FakeDriver()
        out = price_run.propose_top(drv, None, 1, [sugg(1, 5), sugg(2, 9), sugg(3, 7), sugg(4, 1, "hold")], 2)
        self.assertEqual([p for p, _ in drv.sent], [2, 3])
        self.assertEqual(len(out), 2)

    def test_skips_products_that_already_have_a_proposal_waiting(self):
        drv = FakeDriver(pending=[2])
        price_run.propose_top(drv, None, 1, [sugg(1, 5), sugg(2, 9)], 5)
        self.assertEqual([p for p, _ in drv.sent], [1])

    def test_sends_confidence_gains_and_evidence_for_the_approval_screen(self):
        drv = FakeDriver()
        price_run.propose_top(drv, None, 1, [sugg(1, 8)], 1)
        kw = drv.sent[0][1]
        self.assertEqual((kw["confidence"], kw["expected_gain_per_day"], kw["expected_gain_conservative_per_day"]), ("assumed", 8.0, 4.0))
        self.assertIn("assumed", kw["evidence"])

    def test_margin_fixes_go_first_and_are_limited_separately(self):
        drv = FakeDriver()
        out = price_run.propose_top(drv, None, 1, [sugg(1, 9), sugg(2, 0, "margin_alert", 90, 99), sugg(3, 0, "margin_alert", 80, 88), sugg(4, 0, "margin_alert", 95, 99.75)], 1, fix_limit=2)
        self.assertEqual([r["kind"] for r in out], ["margin fix", "margin fix", "profit"])
        self.assertEqual([p for p, _ in drv.sent][:2], [2, 3])                  # the biggest relative fixes first
        self.assertEqual(drv.sent[0][1]["confidence"], "rule")

    def test_no_margin_fixes_unless_asked(self):
        drv = FakeDriver()
        price_run.propose_top(drv, None, 1, [sugg(2, 0, "margin_alert", 90, 99)], 5)
        self.assertEqual(drv.sent, [])


if __name__ == "__main__":
    unittest.main()

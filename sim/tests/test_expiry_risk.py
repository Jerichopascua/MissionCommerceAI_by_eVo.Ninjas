import datetime as dt
import unittest
from unittest import mock

from simpeso import agent_service


class Acct:
    token = "t"


TODAY = dt.date(2026, 10, 10)
POLICY = {"configured": True, "autonomyMode": "Approval", "maxDiscountPct": 50, "hardMarginFloorPct": 5, "softMarginFloorPct": 10}
PRODUCTS = [{"id": 7, "name": "Fresh milk", "category": "Dairy", "cost": 60.0, "price": 100.0, "stock": 40.0, "perishable": True},
            {"id": 8, "name": "Bread", "category": "Bakery", "cost": 20.0, "price": 35.0, "stock": 30.0, "perishable": True}]


class FakeDrv:
    def __init__(self, batches, movements=None, policy=None, earlier=None, markdown_status=202):
        self.batches, self.movements_rows = batches, movements or []
        self.policy = POLICY if policy is None else policy
        self.earlier, self.markdown_status = earlier or [], markdown_status
        self.posted, self.markdowns = [], []

    def all_receipts(self, acct, wh):
        return []

    def movements(self, acct, wh, kind="SALE_OUT", after_id=0, since=None):
        return [m for m in self.movements_rows if m["warehouseId"] == wh and m["id"] > after_id and m["transactionDate"][:10] >= (since or "0")]

    def all_batches(self, acct, wh):
        return [b for b in self.batches if b["warehouseId"] == wh]

    def pricing_policy(self, acct):
        return self.policy

    def count_suggestions(self, acct, status="Open", kind=None):
        return self.earlier

    def markdown(self, acct, wh, pid, batch_id, price, reason, ref, source):
        self.markdowns.append((wh, pid, batch_id, price, source))
        return self.markdown_status, ({"priceChangeId": 1} if self.markdown_status == 202 else {"code": "AI_BRANCH_OFF"})

    def post_count_suggestions(self, acct, warehouse_ids, items):
        self.posted.append((warehouse_ids, items))
        return 200, {"added": len(items), "skipped": 0}


def batch(i, pid, qty, days, cost=60.0, wh=1):
    return {"id": i, "warehouseId": wh, "productId": pid, "batchNo": f"B{i}", "qtyOnHand": qty, "cost": cost,
            "expiryDate": (TODAY + dt.timedelta(days=days)).isoformat() + "T00:00:00"}


def sales(pid, per_day, days=14, wh=1):
    return [{"id": 1000 + k, "warehouseId": wh, "productId": pid, "qtyOut": per_day,
             "transactionDate": (TODAY - dt.timedelta(days=k)).isoformat() + "T10:00:00"} for k in range(days)]


class ExpiryRiskTests(unittest.TestCase):
    def go(self, drv, **kw):
        with mock.patch("simpeso.price_run.browse", return_value=PRODUCTS):
            summary = agent_service.loss_prevention_handler(drv, Acct(), [1], per_branch=5, as_of=TODAY, today=TODAY, **kw)()
        return summary, [i for i in drv.posted[0][1] if i.get("Kind") == "SellFast"]

    def test_a_batch_that_will_not_sell_in_time_is_listed_with_the_amount_at_risk_and_a_discount(self):
        drv = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5))                  # 40 units, 2 days, about 5 a day: about 30 would be left
        summary, fast = self.go(drv)
        self.assertEqual(len(fast), 1)
        f = fast[0]
        self.assertEqual((f["BatchId"], f["DaysLeft"], f["BatchQty"]), (1, 2, 40))
        self.assertAlmostEqual(f["UnitsAtRisk"], 30, delta=2)
        self.assertGreater(f["ValueAtRisk"], 1000)
        self.assertGreater(f["SuggestedDiscountPct"], 0)
        self.assertLess(f["SuggestedPrice"], 100)
        self.assertIn("expire in 2 day(s)", f["Reason"])
        self.assertIn("markdown", f["Reason"])
        self.assertIn("1 batch(es) may expire unsold", summary)

    def test_the_nearest_batches_also_get_a_markdown_proposed_as_ai_through_pesowebs_rules(self):
        drv = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5))
        summary, fast = self.go(drv)
        self.assertEqual(len(drv.markdowns), 1)
        self.assertEqual(drv.markdowns[0][4], "Ai")
        self.assertEqual(fast[0]["ProposalStatus"], "Proposed")
        self.assertIn("1 markdown(s) proposed", summary)

    def test_no_markdown_is_proposed_further_out_or_without_pricing_rules_or_when_autonomy_is_off(self):
        far = FakeDrv([batch(1, 7, 40, 9)], sales(7, 1))                  # 9 days away: listed, not proposed
        _, fast = self.go(far)
        self.assertEqual(far.markdowns, [])
        self.assertEqual(len(fast), 1)
        unset = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5), policy={"configured": False, "autonomyMode": "Off"})
        _, fast = self.go(unset)
        self.assertEqual(unset.markdowns, [])
        self.assertIn("Set the pricing rules", fast[0]["Reason"])
        off = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5), policy={"configured": True, "autonomyMode": "Off"})
        self.go(off)
        self.assertEqual(off.markdowns, [])

    def test_a_batch_already_proposed_in_an_earlier_run_is_not_proposed_again(self):
        drv = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5), earlier=[{"warehouseId": 1, "batchId": 1, "proposalStatus": "Proposed"}])
        _, fast = self.go(drv)
        self.assertEqual(drv.markdowns, [])
        self.assertEqual(fast[0]["ProposalStatus"], "Proposed")

    def test_a_refusal_by_pesoweb_is_recorded_with_its_code(self):
        drv = FakeDrv([batch(1, 7, 40, 2)], sales(7, 5), markdown_status=422)
        _, fast = self.go(drv)
        self.assertEqual(fast[0]["ProposalStatus"], "Refused: AI_BRANCH_OFF")

    def test_expired_stock_is_listed_to_write_off_and_never_discounted(self):
        drv = FakeDrv([batch(1, 7, 10, -3)], sales(7, 5))
        _, fast = self.go(drv)
        f = fast[0]
        self.assertEqual(f["DaysLeft"], -3)
        self.assertIsNone(f["SuggestedDiscountPct"])
        self.assertIn("write them off", f["Reason"])
        self.assertEqual(drv.markdowns, [])

    def test_a_batch_that_will_sell_in_time_is_left_out_and_fefo_counts_units_that_expire_sooner(self):
        _, fast = self.go(FakeDrv([batch(1, 7, 8, 3)], sales(7, 5)))      # 5 a day for 3 days is 15, more than 8
        self.assertEqual(fast, [])
        # the earlier batch sells first and uses up the 10 expected sales, so the later one is at risk although 30 < 5 x 3 x ... on its own
        _, fast = self.go(FakeDrv([batch(1, 7, 10, 2), batch(2, 7, 30, 3)], sales(7, 5)))
        later = [i for i in fast if i["BatchId"] == 2]
        self.assertEqual(len(later), 1)
        self.assertGreater(later[0]["UnitsAtRisk"], 10)

    def test_a_product_that_has_not_sold_is_listed_but_gets_no_made_up_discount(self):
        drv = FakeDrv([batch(1, 7, 20, 4)], [])
        _, fast = self.go(drv)
        self.assertIsNone(fast[0]["SuggestedDiscountPct"])
        self.assertIn("has not sold in this period", fast[0]["Reason"])
        self.assertEqual(drv.markdowns, [])

    def test_batches_with_no_expiry_date_or_nothing_on_hand_are_ignored(self):
        plain = batch(1, 7, 10, 2)
        plain["expiryDate"] = None
        empty = batch(2, 7, 0, 2)
        _, fast = self.go(FakeDrv([plain, empty], sales(7, 5)))
        self.assertEqual(fast, [])


if __name__ == "__main__":
    unittest.main()

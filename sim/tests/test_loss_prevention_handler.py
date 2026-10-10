import datetime as dt
import unittest
from unittest import mock

from simpeso import agent_service


class Acct:
    token = "t"


class FakeDrv:
    def __init__(self, receipts, movements, status=200):
        self._receipts, self._movements, self.status = receipts, movements, status
        self.posted = []

    def all_receipts(self, acct, wh):
        return [r for r in self._receipts if r["warehouseId"] == wh]

    def movements(self, acct, wh, kind="SALE_OUT", after_id=0, since=None):
        return [m for m in self._movements if m["warehouseId"] == wh and m["id"] > after_id and m["transactionDate"][:10] >= (since or "0")]

    def all_batches(self, acct, wh):
        return []                                   # these tests are about counting; expiry risk has its own tests

    def pricing_policy(self, acct):
        return {}

    def count_suggestions(self, acct, status="Open", kind=None):
        return []

    def post_count_suggestions(self, acct, warehouse_ids, items):
        self.posted.append((warehouse_ids, items))
        return self.status, {"added": len(items), "skipped": 0}


def receipt(i, wh, pid, qty, cost, report):
    return {"id": i, "warehouseId": wh, "productId": pid, "quantity": qty, "unitCost": cost, "hasReceivingReport": report}


PRODUCTS = [{"id": 7, "name": "A", "category": "X", "cost": 60.0, "price": 100.0, "stock": 10.0, "perishable": False},
            {"id": 8, "name": "B", "category": "X", "cost": 5.0, "price": 9.0, "stock": 10.0, "perishable": False},
            {"id": 9, "name": "C", "category": "X", "cost": 0.0, "price": 0.0, "stock": 1.0, "perishable": False}]


class LossPreventionHandlerTests(unittest.TestCase):
    def run_handler(self, drv, **kw):
        with mock.patch("simpeso.price_run.browse", return_value=PRODUCTS):
            return agent_service.loss_prevention_handler(drv, Acct(), [1], per_branch=5, as_of=dt.date(2026, 10, 10), **kw)()

    def test_an_unreported_delivery_comes_first_and_is_worded_for_a_person(self):
        receipts = [receipt(1, 1, 7, 10, 60, True), receipt(2, 1, 8, 10, 5, True),         # opening stock (first receipt of a product)
                    receipt(3, 1, 8, 900, 5, False),                                        # a delivery nobody reported
                    receipt(4, 1, 7, 10, 60, True)]                                         # a reported one
        moves = [{"id": 1, "warehouseId": 1, "productId": 7, "qtyOut": 40, "transactionDate": "2026-10-05T10:00:00"}]
        drv = FakeDrv(receipts, moves)
        summary = self.run_handler(drv)
        items = drv.posted[0][1]
        self.assertEqual(items[0]["ProductId"], 8)
        self.assertIn("no receiving report", items[0]["Reason"])
        self.assertTrue(items[0]["Reason"][0].isupper())
        self.assertIn("1 with an unreported delivery", summary)

    def test_a_product_with_no_cost_is_left_out_and_one_that_has_not_sold_is_not_called_a_fast_seller(self):
        drv = FakeDrv([receipt(1, 1, 7, 10, 60, True)], [])
        self.run_handler(drv)
        ids = [i["ProductId"] for i in drv.posted[0][1]]
        self.assertNotIn(9, ids)                                       # no cost recorded: nothing to rank it by
        reason = next(i["Reason"] for i in drv.posted[0][1] if i["ProductId"] == 7)
        self.assertNotIn("fast seller", reason)
        self.assertIn("has not sold in this period", reason)

    def test_with_nothing_at_all_an_empty_list_is_posted_so_old_suggestions_are_replaced(self):
        drv = FakeDrv([], [])
        with mock.patch("simpeso.price_run.browse", return_value=[]):
            summary = agent_service.loss_prevention_handler(drv, Acct(), [1], per_branch=5, as_of=dt.date(2026, 10, 10))()
        self.assertEqual(drv.posted[0][1], [])
        self.assertIn("0 products to count first", summary)

    def test_a_product_with_nothing_on_the_shelf_at_the_branch_is_not_listed(self):
        products = [dict(PRODUCTS[0], stock=0.0), PRODUCTS[1]]
        drv = FakeDrv([receipt(1, 1, 7, 10, 60, True), receipt(2, 1, 7, 99, 60, False)], [])
        with mock.patch("simpeso.price_run.browse", return_value=products):
            agent_service.loss_prevention_handler(drv, Acct(), [1], per_branch=5, as_of=dt.date(2026, 10, 10))()
        ids = [i["ProductId"] for i in drv.posted[0][1]]
        self.assertNotIn(7, ids)
        self.assertIn(8, ids)

    def test_sales_after_the_as_of_day_do_not_count(self):
        receipts = [receipt(1, 1, 7, 10, 60, True)]
        moves = [{"id": 1, "warehouseId": 1, "productId": 7, "qtyOut": 500, "transactionDate": "2026-12-01T10:00:00"}]
        drv = FakeDrv(receipts, moves)
        self.run_handler(drv)
        # product 7 sold 0 inside the window: it may still be listed (value on the shelf) but its score is only the baseline
        score_with_future = [i["Score"] for i in drv.posted[0][1] if i["ProductId"] == 7]
        drv2 = FakeDrv(receipts, [])
        self.run_handler(drv2)
        self.assertEqual(score_with_future, [i["Score"] for i in drv2.posted[0][1] if i["ProductId"] == 7])

    def test_a_refusal_fails_the_run_with_the_reason(self):
        with self.assertRaises(RuntimeError):
            self.run_handler(FakeDrv([], [], status=422))


if __name__ == "__main__":
    unittest.main()

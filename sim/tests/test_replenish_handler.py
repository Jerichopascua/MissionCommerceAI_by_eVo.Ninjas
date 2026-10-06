import unittest

from simpeso import agent_service as ag


class Acct:
    token = "t"


def row(pid, stock, perishable=False, cost=10.0):
    return {"id": pid, "productName": f"P{pid}", "categoryName": "Cat", "cost": cost, "price": cost * 1.3, "quantity": stock, "monitorExpiry": perishable}


class FakeDriver:
    def __init__(self, products, movements=None, post_status=200):
        self.products, self._movements, self.post_status = products, movements or [], post_status
        self.posted = []

    def _call(self, method, path, token=None, json_body=None, raw=False, **kw):
        if path.startswith("/api/Inventory/Products"):
            return {"data": self.products, "recordsTotal": len(self.products)}
        raise AssertionError(path)

    def movements(self, acct, wh, kind, after_id=0, since=None):
        return self._movements

    def post_replenish(self, acct, warehouse_ids, items):
        self.posted.append((warehouse_ids, items))
        return self.post_status, {"added": len(items)}


class ReplenishHandlerTests(unittest.TestCase):
    def test_model_rates_drive_suggestions_for_products_that_will_not_last(self):
        drv = FakeDriver([row(1, 3), row(2, 500), row(3, 2)])
        model = {"rates": {"7:1": 4.0, "7:2": 4.0}}                      # product 3 has no rate: no evidence
        msg = ag.replenish_handler(drv, Acct(), [7], model)()
        warehouses, items = drv.posted[0]
        self.assertEqual(warehouses, [7])
        self.assertEqual([i["ProductId"] for i in items], [1])            # 2 has plenty of stock, 3 has no demand data
        self.assertEqual(items[0]["WarehouseId"], 7)
        self.assertEqual(items[0]["Confidence"], "limited")               # two baseline days is not much
        self.assertGreater(items[0]["SuggestedQty"], 0)
        self.assertIn("1 reorder suggestions", msg)

    def test_a_perishable_is_capped_by_its_shelf_life(self):
        drv = FakeDriver([row(1, 0, perishable=False), row(2, 0, perishable=True)])
        model = {"rates": {"7:1": 4.0, "7:2": 4.0}}
        ag.replenish_handler(drv, Acct(), [7], model, perishable_shelf_days=2)()
        by = {i["ProductId"]: i["SuggestedQty"] for i in drv.posted[0][1]}
        self.assertEqual(by[2], 8.0)                                     # 2 days of sales
        self.assertGreater(by[1], by[2])

    def test_dated_sales_are_used_when_there_is_no_model(self):
        moves = [{"productId": 1, "qtyOut": 4, "transactionDate": f"2026-10-0{d}T10:00:00"} for d in range(1, 8)]
        drv = FakeDriver([row(1, 3)], movements=moves)
        ag.replenish_handler(drv, Acct(), [7], None, window_days=7)()
        items = drv.posted[0][1]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["Confidence"], "learned")              # seven days of sales

    def test_a_refusal_from_pesoweb_fails_the_run_with_its_answer(self):
        drv = FakeDriver([row(1, 0)], post_status=422)
        with self.assertRaises(RuntimeError):
            ag.replenish_handler(drv, Acct(), [7], {"rates": {"7:1": 4.0}})()


if __name__ == "__main__":
    unittest.main()

import io
import json
import logging
import unittest
from unittest import mock

import requests

from simpeso import driver as drv
from simpeso.verticals import ProductSpec


class FakeResp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = json.dumps(body) if body is not None else ""

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class FakeSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make(replies):
    s = FakeSession(replies)
    return drv.PesoWebDriver("http://x:1/", "run-1", session=s), s


def acct():
    return drv.Account("o@x", "pw", "SECRET-TOKEN", 7, 11, 5)


class DriverTests(unittest.TestCase):
    def test_register_is_json_and_returns_account(self):
        d, s = make([FakeResp(200, {"token": "a.e30.c", "tenantID": 9, "defaultWarehouseId": 4})])
        a = d.register("Co", "A", "B", "e@x", "secret1")
        method, url, kw = s.requests[0]
        self.assertEqual((method, url), ("POST", "http://x:1/api/Auth/Register"))
        self.assertEqual(kw["json"]["ConfirmPassword"], "secret1")
        self.assertEqual(kw["headers"]["X-Sim-Run"], "run-1")
        self.assertEqual((a.tenant_id, a.warehouse_id), (9, 4))

    def test_category_and_sale_are_multipart_with_booleans_lowercase(self):
        d, s = make([FakeResp(200, {"id": 3}), FakeResp(201, {"id": 8, "totalAmount": 100})])
        d.add_category(acct(), "Dairy")
        sale = d.sell(acct(), 11, 2, [(5, 2), (6, 1)], "Cash", 100)
        cat_kw, sale_kw = s.requests[0][2], s.requests[1][2]
        self.assertIn("files", cat_kw)
        self.assertEqual(cat_kw["files"]["CategoryName"], (None, "Dairy"))
        self.assertEqual(sale_kw["files"]["saleDetails[1].productId"], (None, "6"))
        self.assertEqual(sale_kw["headers"]["Authorization"], "Bearer SECRET-TOKEN")
        self.assertEqual(sale["id"], 8)

    def test_expiry_product_flags_and_plain_product(self):
        d, s = make([FakeResp(200, {"id": 1}), FakeResp(200, {"id": 2})])
        basics = {"unit": 1, "tax": 1, "brand": 1}
        d.add_product(acct(), ProductSpec("A", "Milk", "Dairy", 10, 15, True, (3, 7), 3), 1, basics)
        d.add_product(acct(), ProductSpec("B", "Oil", "Fluids", 10, 15, False), 1, basics)
        exp, plain = s.requests[0][2]["files"], s.requests[1][2]["files"]
        self.assertEqual(exp["BatchTracking"], (None, "true"))
        self.assertEqual(exp["ExpiryAlertDays"], (None, "3"))
        self.assertNotIn("BatchTracking", plain)
        self.assertEqual(plain["HasVariants"], (None, "false"))

    def test_purchase_lines_carry_batch_fields(self):
        d, s = make([FakeResp(200, {"id": 5})])
        d.receive_stock(acct(), 11, 3, [{"product_id": 9, "unit_cost": 60, "quantity": 20, "batch_no": "B1",
                                          "expiry_date": "2026-10-20", "manufacturing_date": "2026-10-01"}], "2026-10-05")
        f = s.requests[0][2]["files"]
        self.assertEqual(f["purchaseDetails[0].batchNo"], (None, "B1"))
        self.assertEqual(f["PaidAmount"], (None, "1200"))
        self.assertEqual(f["OrderStatus"], (None, "1"))

    def test_tier_limit_is_a_refusal_not_a_crash(self):
        msg = {"message": "Branch limit reached for your subscription plan. Maximum allowed branches: 1."}
        d, _ = make([FakeResp(400, msg)])
        with self.assertRaises(drv.DriverRefusal) as ctx:
            d.add_branch(acct(), "B2", "Manila", 2)
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(len(d.refusals), 1)

    def test_other_errors_raise_and_do_not_leak_the_token(self):
        d, _ = make([FakeResp(500, {"message": "boom"})])
        with self.assertRaises(drv.DriverError) as ctx:
            d.sell(acct(), 11, 2, [(5, 1)])
        self.assertNotIn("SECRET-TOKEN", str(ctx.exception))
        self.assertNotIn("SECRET-TOKEN", repr(acct()))

    def test_connection_errors_retry_then_succeed(self):
        with mock.patch("time.sleep"):
            d, s = make([requests.ConnectionError("down"), requests.ConnectionError("down"), FakeResp(200, {"id": 1})])
            self.assertEqual(d.add_category(acct(), "X"), 1)
        self.assertEqual(len(s.requests), 3)

    def test_connection_errors_give_up_after_three(self):
        with mock.patch("time.sleep"):
            d, _ = make([requests.ConnectionError("down")] * 3)
            with self.assertRaises(drv.DriverError):
                d.add_category(acct(), "X")

    def test_no_token_in_log_output(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger().addHandler(handler)
        try:
            d, _ = make([FakeResp(200, {"id": 1})])
            d.add_category(acct(), "X")
        finally:
            logging.getLogger().removeHandler(handler)
        self.assertNotIn("SECRET-TOKEN", stream.getvalue())

    def test_user_id_comes_from_the_sid_claim(self):
        import base64
        payload = base64.urlsafe_b64encode(json.dumps(
            {"http://schemas.xmlsoap.org/ws/2005/05/identity/claims/sid": "42"}).encode()).decode().rstrip("=")
        d, _ = make([FakeResp(200, {"token": f"h.{payload}.s", "tenantID": 1, "defaultWarehouseId": 1})])
        self.assertEqual(d.login("a@x", "pw").user_id, 42)


if __name__ == "__main__":
    unittest.main()

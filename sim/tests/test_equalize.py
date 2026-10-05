import datetime as dt
import unittest
from types import SimpleNamespace

from simpeso import equalize as eq


class Prod:
    def __init__(self, code, cost, expiry=None):
        self.code, self.cost, self.expiry = code, cost, expiry


class FakeDriver:
    def __init__(self, batches):
        self.batches, self.received = batches, []

    def all_batches(self, owner, wh):
        return self.batches.get(wh, [])

    def receive_stock(self, owner, wh, supplier, lines, date):
        self.received.append((wh, supplier, lines, date))


def world(batches, products=None):
    products = products or [Prod("A", 10), Prod("B", 20), Prod("M", 5, expiry=3)]
    ctx = SimpleNamespace(
        driver=FakeDriver(batches), owner=lambda ck: "owner",
        state={"companies": {"c1": {"products": {"A": 1, "B": 2, "M": 3}, "suppliers": [77]}}},
        cmap={"c1": SimpleNamespace(catalog=products)})
    hooks = SimpleNamespace(live_branches=lambda: [("c1", "c1-b1", 100)], rates={}, _catalog={})
    return ctx, hooks


class TopUpTests(unittest.TestCase):
    def test_tops_up_only_what_is_short_to_the_same_level(self):
        ctx, hooks = world({100: [{"productId": 1, "qtyOnHand": 25}, {"productId": 2, "qtyOnHand": 60}, {"productId": 1, "qtyOnHand": 5}]})
        n = eq.top_up_stock(ctx, hooks, level=60, today=dt.date(2026, 10, 6))
        wh, supplier, lines, _ = ctx.driver.received[0]
        got = {l["product_id"]: l["quantity"] for l in lines}
        self.assertEqual(got, {1: 30, 3: 60})                 # A had 30 (25+5), B is full, M has none
        self.assertEqual((n, supplier), (2, 77))

    def test_two_worlds_end_at_the_same_level_whatever_they_started_with(self):
        a, ha = world({100: [{"productId": 1, "qtyOnHand": 3}]})
        b, hb = world({100: [{"productId": 1, "qtyOnHand": 50}, {"productId": 2, "qtyOnHand": 10}]})
        eq.top_up_stock(a, ha, 60)
        eq.top_up_stock(b, hb, 60)
        level = lambda ctx, base: {pid: base.get(pid, 0) + sum(l["quantity"] for _, _, ls, _ in ctx.driver.received for l in ls if l["product_id"] == pid) for pid in (1, 2, 3)}
        self.assertEqual(level(a, {1: 3}), {1: 60, 2: 60, 3: 60})
        self.assertEqual(level(b, {1: 50, 2: 10}), {1: 60, 2: 60, 3: 60})

    def test_perishable_ordinary_stock_gets_a_far_expiry_date(self):
        ctx, hooks = world({})
        eq.top_up_stock(ctx, hooks, 60, today=dt.date(2026, 10, 6))
        lines = {l["product_id"]: l for l in ctx.driver.received[0][2]}
        self.assertEqual(lines[3]["expiry_date"], "2026-12-05")
        self.assertNotIn("expiry_date", lines[1])
        self.assertNotIn("batch_no", lines[1])               # the driver wants dates on every batched line, so ordinary products carry none

    def test_a_big_top_up_is_split_into_several_purchases(self):
        products = [Prod(f"P{i}", 5) for i in range(300)]
        ctx, hooks = world({}, products)
        ctx.state["companies"]["c1"]["products"] = {p.code: i + 1 for i, p in enumerate(products)}
        eq.top_up_stock(ctx, hooks, 60)
        sizes = [len(ls) for _, _, ls, _ in ctx.driver.received]
        self.assertEqual(sizes, [120, 120, 60])


class AlignRatesTests(unittest.TestCase):
    def test_rates_are_matched_by_branch_and_product_code_across_different_ids(self):
        src = SimpleNamespace(live_branches=lambda: [("c1", "c1-b1", 100)], rates={(100, 1): 2.5, (100, 2): 4.0},
                              _catalog={1: {"company": "c1", "code": "A"}, 2: {"company": "c1", "code": "B"}})
        dst = SimpleNamespace(live_branches=lambda: [("c1", "c1-b1", 900)], rates={(900, 11): 99.0},
                              _catalog={11: {"company": "c1", "code": "A"}, 12: {"company": "c1", "code": "B"}, 13: {"company": "c1", "code": "Z"}})
        n = eq.align_rates(src, dst)
        self.assertEqual(dst.rates, {(900, 11): 2.5, (900, 12): 4.0})
        self.assertEqual(n, 2)


if __name__ == "__main__":
    unittest.main()

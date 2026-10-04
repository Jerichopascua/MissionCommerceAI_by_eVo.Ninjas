import unittest

from missionai import detectors as d


_ids = iter(range(1, 10_000))


def receipt(wh, pid, qty, cost=10, reported=False, id=None):
    return {"id": id if id is not None else next(_ids), "warehouseId": wh, "productId": pid, "quantity": qty,
            "unitCost": cost, "hasReceivingReport": reported}


def opened(wh, pid):
    """Opening stock for the SKU: its first receipt, which never counts as a delivery."""
    return receipt(wh, pid, 100, reported=False, id=0)


class RankTests(unittest.TestCase):
    def test_unreported_delivery_outranks_a_reported_one(self):
        receipts = [opened(1, 1), opened(1, 2), receipt(1, 1, 24, reported=False), receipt(1, 2, 24, reported=True)]
        t = d.rank_count_targets(receipts, {(1, 1): 5, (1, 2): 5}, {(1, 1): 10, (1, 2): 10}, k=2)
        self.assertEqual([x.product_id for x in t], [1, 2])
        self.assertIn("delivered without a receiving report", t[0].reasons)

    def test_high_value_outranks_low_value_when_nothing_is_unreported(self):
        t = d.rank_count_targets([], {(1, 1): 5, (1, 2): 5}, {(1, 1): 500, (1, 2): 5}, k=2)
        self.assertEqual(t[0].product_id, 1)

    def test_k_is_per_warehouse(self):
        costs = {(w, p): 10 for w in (1, 2) for p in range(1, 6)}
        t = d.rank_count_targets([], {}, costs, k=2)
        self.assertEqual(sorted(x.warehouse_id for x in t), [1, 1, 2, 2])

    def test_already_counted_pairs_are_skipped(self):
        t = d.rank_count_targets([], {}, {(1, 1): 10, (1, 2): 10}, k=5, counted={(1, 1)})
        self.assertEqual([x.product_id for x in t], [2])

    def test_opening_stock_without_a_report_does_not_raise_a_count_priority(self):
        t = d.rank_count_targets([opened(1, 1)], {(1, 1): 5, (1, 2): 5}, {(1, 1): 10, (1, 2): 10}, k=2)
        self.assertTrue(all("delivered without a receiving report" not in x.reasons for x in t))

    def test_empty_inputs_are_safe(self):
        self.assertEqual(d.rank_count_targets([], {}, {}, k=3), [])


class FindingTests(unittest.TestCase):
    def count(self, wh, pid, system, counted, branch="c1-b1"):
        return {"warehouse_id": wh, "product_id": pid, "branch": branch, "system_qty": system, "counted_qty": counted}

    def test_short_count_after_unreported_delivery_is_typed_as_that(self):
        f = d.findings_from_counts([self.count(1, 1, 24, 17)], [opened(1, 1), receipt(1, 1, 24)])
        self.assertEqual(f[0]["type"], d.UNREPORTED_SHORT_DELIVERY)
        self.assertEqual(f[0]["shortfall_units"], 7)
        self.assertIn("count differs from system", f[0]["evidence"])

    def test_short_count_without_a_delivery_signal_is_hidden_shrink(self):
        f = d.findings_from_counts([self.count(1, 2, 30, 27)], [opened(1, 2), receipt(1, 1, 24)])
        self.assertEqual(f[0]["type"], d.HIDDEN_SHRINK)

    def test_opening_stock_is_not_a_delivery_so_a_short_count_there_is_hidden_shrink(self):
        f = d.findings_from_counts([self.count(1, 1, 40, 37)], [opened(1, 1)])
        self.assertEqual(f[0]["type"], d.HIDDEN_SHRINK)

    def test_matching_counts_produce_no_finding(self):
        self.assertEqual(d.findings_from_counts([self.count(1, 1, 24, 24)], []), [])

    def test_overage_is_not_a_shortage_finding(self):
        self.assertEqual(d.findings_from_counts([self.count(1, 1, 24, 26)], []), [])

    def test_duplicate_counts_do_not_emit_twice(self):
        f = d.findings_from_counts([self.count(1, 1, 24, 20), self.count(1, 1, 24, 20)], [])
        self.assertEqual(len(f), 1)

    def test_finding_wording_has_no_accusation(self):
        f = d.findings_from_counts([self.count(1, 1, 24, 17)], [opened(1, 1), receipt(1, 1, 24)])
        for bad in ("theft", "stole", "thief", "fraud"):
            self.assertNotIn(bad, f[0]["evidence"].lower())

    def test_small_difference_under_tolerance_is_ignored(self):
        self.assertEqual(d.findings_from_counts([self.count(1, 1, 24, 23.5)], []), [])


if __name__ == "__main__":
    unittest.main()

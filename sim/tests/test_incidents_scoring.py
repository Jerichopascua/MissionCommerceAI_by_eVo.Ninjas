import json
import tempfile
import unittest
from pathlib import Path

from simpeso import incidents as inc, scoring, world


def mk(i, kind, branch, wh, **detail):
    x = inc.Incident(f"inc-{i}", kind, "c1", branch, 0, 10, detail, warehouse_id=wh)
    x.expected_exception = inc.EXPECTED_EXCEPTION[kind]
    return x


def exc(i, typ, wh, variance=None):
    return {"id": i, "type": typ, "warehouseId": wh, "evidenceJson": json.dumps({"variance": variance}) if variance is not None else None}


class GoldenRunTests(unittest.TestCase):
    """Five known incidents, scripted exceptions and AI findings, exact split asserted."""

    def setUp(self):
        self.truth = [
            mk(1, inc.CASH_SHORT, "c1-b1", 11, amount=200),
            mk(2, inc.CASH_SHORT, "c1-b2", 12, amount=100),
            mk(3, inc.NEAR_EXPIRY_BATCH, "c1-b3", 13, product_code="X"),
            mk(4, inc.UNREPORTED_SHORT_DELIVERY, "c1-b4", 14, product_code="Y"),
            mk(5, inc.HIDDEN_SHRINK, "c1-b5", 15, product_code="Z"),
        ]
        self.exceptions = [
            exc(100, "CASH_VARIANCE", 11, -200),     # explains incident 1
            exc(101, "CASH_VARIANCE", 12, -3),       # rounding noise: wrong amount, so incident 2 stays unmatched here
            exc(102, "EXPIRY_ALERT", 13),            # explains incident 3
            exc(103, "LOW_STOCK", 14),               # unrelated
        ]

    def test_exact_split_without_ai(self):
        card = scoring.score(self.truth, self.exceptions)
        got = {o.incident_id: o.status for o in card.outcomes}
        self.assertEqual(got, {"inc-1": "caught", "inc-2": "undetected", "inc-3": "caught",
                               "inc-4": "undetected", "inc-5": "undetected"})
        self.assertEqual(sorted(card.other_exceptions), [101, 103])
        self.assertAlmostEqual(card.coverage, 0.4)

    def test_ai_findings_close_the_gap_one_to_one(self):
        ai = [{"id": "a1", "type": inc.HIDDEN_SHRINK, "branch": "c1-b5"},
              {"id": "a2", "type": inc.UNREPORTED_SHORT_DELIVERY, "branch": "c1-b4"},
              {"id": "a3", "type": inc.HIDDEN_SHRINK, "branch": "c1-b5"}]    # duplicate finding explains nothing more
        card = scoring.score(self.truth, self.exceptions, ai)
        s = card.summary()
        self.assertEqual((s["caught"], s["ai_found"], s["undetected"]), (2, 2, 1))
        self.assertAlmostEqual(s["coverage"], 0.8)
        self.assertEqual(s["by_type"][inc.HIDDEN_SHRINK]["ai_found"], 1)

    def test_one_exception_cannot_explain_two_incidents(self):
        truth = [mk(1, inc.CASH_SHORT, "b", 11, amount=100), mk(2, inc.CASH_SHORT, "b", 11, amount=100)]
        card = scoring.score(truth, [exc(1, "CASH_VARIANCE", 11, -100)])
        self.assertEqual([o.status for o in card.outcomes], ["caught", "undetected"])

    def test_cash_shortage_tolerates_natural_counting_noise_but_not_a_different_amount(self):
        truth = [mk(1, inc.CASH_SHORT, "b", 11, amount=100)]
        self.assertEqual(scoring.score(truth, [exc(1, "CASH_VARIANCE", 11, -95)]).outcomes[0].status, "caught")
        self.assertEqual(scoring.score(truth, [exc(1, "CASH_VARIANCE", 11, -300)]).outcomes[0].status, "undetected")

    def test_expiry_alert_must_be_for_the_injected_batch(self):
        truth = [mk(1, inc.NEAR_EXPIRY_BATCH, "b", 13, batch_id=77)]
        baseline = {"id": 1, "type": "EXPIRY_ALERT", "warehouseId": 13, "referenceNo": "batch-5"}
        ours = {"id": 2, "type": "EXPIRY_ALERT", "warehouseId": 13, "referenceNo": "batch-77"}
        self.assertEqual(scoring.score(truth, [baseline]).outcomes[0].status, "undetected")
        card = scoring.score(truth, [baseline, ours])
        self.assertEqual((card.outcomes[0].status, card.outcomes[0].evidence_id, card.other_exceptions), ("caught", "2", [1]))

    def test_wrong_branch_is_not_a_match(self):
        card = scoring.score([mk(1, inc.NEAR_EXPIRY_BATCH, "b", 13)], [exc(1, "EXPIRY_ALERT", 99)])
        self.assertEqual(card.outcomes[0].status, "undetected")

    def test_empty_is_zero_coverage_not_a_crash(self):
        self.assertEqual(scoring.score([], []).coverage, 0.0)


class PlanTests(unittest.TestCase):
    def test_five_incidents_on_distinct_branches_and_deterministic(self):
        plan = world.plan_group(21, "starter")
        a = inc.plan_incidents(plan, 21, 0)
        b = inc.plan_incidents(plan, 21, 0)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)
        self.assertEqual(len({i.branch for i in a}), 5)
        self.assertEqual(sorted(i.type for i in a), sorted(inc.DAILY_MIX))

    def test_perishable_incident_only_in_a_company_with_expiry(self):
        for seed in range(1, 25):
            plan = world.plan_group(seed, "smoke")
            cmap = {c.key: c for c in plan.companies}
            for i in inc.plan_incidents(plan, seed, 0):
                if i.type == inc.NEAR_EXPIRY_BATCH:
                    self.assertTrue(any(p.expiry for p in cmap[i.company].catalog))

    def test_no_incident_starts_on_a_branch_that_opens_mid_run(self):
        plan = world.plan_group(21, "starter")
        mid = {e["branch"] for e in plan.expansions}
        self.assertFalse(mid & {i.branch for i in inc.plan_incidents(plan, 21, 0)})

    def test_ledger_roundtrip_and_expected_exception(self):
        ledger = inc.Ledger()
        ledger.add(inc.Incident("x", inc.CASH_SHORT, "c1", "c1-b1", 0, 22, {"amount": 100}, 11))
        ledger.add(inc.Incident("y", inc.HIDDEN_SHRINK, "c1", "c1-b2", 0, 14, {"units": 3}, 12))
        path = Path(tempfile.mkdtemp()) / "ledger.json"
        ledger.save(path)
        again = inc.Ledger.load(path)
        self.assertEqual(again.incidents, ledger.incidents)
        self.assertEqual([i.expected_exception for i in again.incidents], ["CASH_VARIANCE", None])

    def test_ledger_wording_has_no_accusation(self):
        plan = world.plan_group(21, "starter")
        text = json.dumps([i.detail for i in inc.plan_incidents(plan, 21, 0)]).lower()
        for bad in ("thief", "theft", "stole", "fraud"):
            self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()

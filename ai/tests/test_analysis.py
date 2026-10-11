import datetime as dt
import unittest

from missionai import analysis, insight

NOW = "2026-10-11T12:00:00"


def change(status, code=None, source="Ai"):
    return {"source": source, "status": status, "guardrailCode": code}


def ok():
    return change("Applied", "OK")


def person():
    return change("Rejected", "REJECTED_BY_USER")


def lapsed():
    return change("Rejected", "PROPOSAL_EXPIRED")


IMPACT = {"available": True, "windowDays": 6, "switchDate": "2026-10-05T00:00:00", "aiPriceChanges": 61,
          "before": {"metrics": {"sales": 100000, "marginPct": 12.0, "wastePct": 3.0}},
          "after": {"metrics": {"sales": 141913, "marginPct": 13.8, "wastePct": 1.2}},
          "change": {"salesPct": 41.9, "marginPts": 1.8, "wastePts": -1.8, "marginPerDay": 3269.14},
          "control": {"available": False}, "branches": []}


class Effect(unittest.TestCase):
    def test_the_effect_is_stated_with_its_caveat(self):
        n = analysis.effect_so_far({"impact": IMPACT})
        self.assertEqual(n["kind"], "Analysis")
        self.assertIn("margin per day +3269 pesos", n["body"])
        self.assertIn("Indicative, not proof", n["body"])
        self.assertEqual(n["severity"], "Good")

    def test_no_earlier_period_is_said_plainly(self):
        imp = dict(IMPACT, before={"metrics": {"sales": 0}})
        n = analysis.effect_so_far({"impact": imp})
        self.assertIn("no earlier period", n["body"])
        self.assertEqual(n["severity"], "Watch")

    def test_nothing_is_said_when_there_is_no_data(self):
        self.assertIsNone(analysis.effect_so_far({"impact": {"available": False}}))


class Control(unittest.TestCase):
    def test_ai_against_control_reports_the_difference(self):
        imp = dict(IMPACT, control={"available": True, "ai": {"branches": 2, "change": {"marginPts": 1.5, "wastePts": -2.0}},
                                    "control": {"branches": 1, "change": {"marginPts": 0.2, "wastePts": -0.1}},
                                    "difference": {"marginPts": 1.3, "wastePts": -1.9, "salesPts": 0.4}})
        n = analysis.ai_vs_control({"impact": imp})
        self.assertIn("2 AI branch(es) against 1 control", n["body"])
        self.assertIn("margin +1.3 points", n["body"])
        self.assertEqual(n["severity"], "Good")

    def test_all_branches_on_means_set_one_aside(self):
        s = {"impact": IMPACT, "branches": [{"pricingEnabled": True}, {"pricingEnabled": True}]}
        n = analysis.control_branch(s)
        self.assertEqual(n["kind"], "Improve")
        self.assertIn("one branch that is similar", n["body"])

    def test_no_advice_when_a_branch_is_already_the_control(self):
        s = {"impact": IMPACT, "branches": [{"pricingEnabled": True}, {"pricingEnabled": False}]}
        self.assertIsNone(analysis.control_branch(s))


class Proposals(unittest.TestCase):
    def test_outcomes_are_counted(self):
        s = {"changes": [change("Applied")] * 6 + [change("Rejected", "BELOW_HARD_FLOOR")] * 3 + [change("Expired")] * 2 + [change("Pending")]}
        n = analysis.proposal_outcomes(s)
        self.assertIn("12 price proposals", n["body"])
        self.assertIn("6 were applied", n["body"])

    def test_too_few_proposals_say_nothing(self):
        self.assertIsNone(analysis.proposal_outcomes({"changes": [change("Applied")] * 2}))
        self.assertEqual(analysis.refusals({"changes": [change("Rejected", "NO_COST")] * 2}), [])

    def test_the_main_refusal_reason_gets_specific_advice(self):
        s = {"policy": {"hardMarginFloorPct": 5, "maxDiscountPct": 50},
             "changes": [change("Rejected", "BELOW_HARD_FLOOR")] * 7 + [change("Applied")] * 3}
        out = analysis.refusals(s)
        self.assertEqual(len(out), 1)
        self.assertIn("7 of 10", out[0]["headline"])
        self.assertIn("unit costs are current", out[0]["body"])
        self.assertIn("5% over cost", out[0]["body"])
        self.assertEqual(out[0]["facts"]["sharePct"], 70)

    def test_manual_proposals_are_not_the_ais(self):
        s = {"changes": [change("Rejected", "BELOW_HARD_FLOOR", source="Manual")] * 9}
        self.assertEqual(analysis.refusals(s), [])


class RealVocabulary(unittest.TestCase):
    """The codes PesoWeb really writes in the price-change log (seen on a simulated company)."""

    def test_ok_and_a_persons_rejection_are_not_rule_refusals(self):
        s = {"changes": [ok()] * 6 + [person()] * 3 + [lapsed()] * 2 + [change("Rejected", "BELOW_HARD_FLOOR")] * 1}
        self.assertEqual(analysis.refusals(s), [])
        n = analysis.proposal_outcomes(s)
        self.assertIn("6 were applied (50%)", n["body"])
        self.assertIn("3 were rejected by a person", n["body"])
        self.assertIn("1 were refused by a rule", n["body"])
        self.assertIn("2 expired", n["body"])

    def test_people_rejecting_often_is_its_own_finding(self):
        s = {"changes": [ok()] * 8 + [person()] * 4}
        n = analysis.person_rejections(s)
        self.assertIn("4 of 12", n["headline"])
        self.assertIn("smaller maximum step", n["body"])

    def test_a_few_rejections_are_normal(self):
        self.assertIsNone(analysis.person_rejections({"changes": [ok()] * 18 + [person()]}))

    def test_expired_proposals_in_the_log_count_even_when_the_queue_is_empty(self):
        s = {"changes": [ok()] * 3 + [lapsed()] * 5, "approvals": {"summary": {"waiting": 0, "oldestMinutes": 0, "expiredJustNow": 0}},
             "policy": {"storeLaneMaxPct": 5}}
        self.assertIn("5 proposal(s) expired", analysis.stale_queue(s)["body"])

    def test_manual_and_ended_changes_are_left_out(self):
        s = {"changes": [change("Rejected", "BELOW_HARD_FLOOR", source="Manual")] * 20 + [change("Ended", "OK")] * 5 + [ok()] * 5}
        self.assertEqual(analysis.refusals(s), [])
        self.assertIn("5 price proposals", analysis.proposal_outcomes(s)["body"])


class Setup(unittest.TestCase):
    def test_missing_pricing_rules_come_first(self):
        n = analysis.pricing_rules({"policy": {"configured": False}})
        self.assertEqual(n["severity"], "Act")
        self.assertIn("cannot make any price proposal", n["body"])

    def test_a_zero_floor_is_a_watch_item(self):
        n = analysis.pricing_rules({"policy": {"configured": True, "hardMarginFloorPct": 0}})
        self.assertIn("0%", n["headline"])

    def test_expiring_proposals_are_flagged(self):
        n = analysis.stale_queue({"approvals": {"summary": {"waiting": 3, "oldestMinutes": 700, "expiredJustNow": 13}},
                                  "policy": {"storeLaneMaxPct": 5}})
        self.assertIn("13 proposal(s) expired", n["body"])
        self.assertIn("up to 5%", n["body"])

    def test_a_healthy_queue_is_quiet(self):
        self.assertIsNone(analysis.stale_queue({"approvals": {"summary": {"waiting": 2, "oldestMinutes": 30, "expiredJustNow": 0}}}))

    def test_features_off_never_run_or_stale_are_listed(self):
        feats = [{"key": "Replenish", "name": "AI Replenish", "buildState": "Built", "canRun": True, "enabled": False},
                 {"key": "Monitoring", "name": "AI Monitoring", "buildState": "Built", "canRun": True, "enabled": True, "lastRun": None},
                 {"key": "Pricing", "name": "AI Pricing", "buildState": "Built", "canRun": True, "enabled": True,
                  "lastRun": {"finishedAt": "2026-10-01T10:00:00"}},
                 {"key": "Insight", "name": "AI Insight", "buildState": "Built", "canRun": True, "enabled": True,
                  "lastRun": {"finishedAt": "2026-10-11T09:00:00"}}]
        out = analysis.feature_use({"features": feats}, dt.datetime(2026, 10, 11, 12))
        heads = [n["headline"] for n in out]
        self.assertIn("AI Replenish is switched off", heads)
        self.assertIn("AI Monitoring has never run", heads)
        self.assertIn("AI Pricing last ran 10 days ago", heads)
        self.assertEqual(len(out), 3)

    def test_waste_above_target_names_the_branch(self):
        s = {"branches": [{"warehouseId": 1, "name": "Main", "wasteTargetPct": 2.0, "pricingEnabled": True}],
             "impact": {"branches": [{"warehouseId": 1, "name": "Main", "aiMarkdowns": 7, "after": {"wastePct": 4.5}}]}}
        n = analysis.waste_targets(s)[0]
        self.assertIn("4.5% against a target of 2%", n["body"])

    def test_a_short_window_asks_for_patience(self):
        n = analysis.too_early({"impact": dict(IMPACT, windowDays=3)})
        self.assertIn("Only 3 days", n["body"])


class Whole(unittest.TestCase):
    def test_actions_come_before_watch_items_and_analysis_comes_first(self):
        s = {"now": NOW, "impact": dict(IMPACT, windowDays=3), "policy": {"configured": False},
             "branches": [{"pricingEnabled": True}, {"pricingEnabled": True}],
             "approvals": {"summary": {"expiredJustNow": 4, "waiting": 0, "oldestMinutes": 0}},
             "changes": [change("Applied")] * 5}
        out = analysis.analyze(s)
        self.assertEqual(out[0]["kind"], "Analysis")
        improve = [n for n in out if n["kind"] == "Improve"]
        self.assertEqual(improve[0]["severity"], "Act")
        sev = [n["severity"] for n in improve]
        self.assertEqual(sev, sorted(sev, key=lambda x: {"Act": 0, "Watch": 1, "Good": 2}[x]))

    def test_every_figure_in_a_finding_is_in_its_facts_or_its_sentence(self):
        s = {"now": NOW, "impact": IMPACT, "policy": {"configured": True, "hardMarginFloorPct": 5, "maxDiscountPct": 50},
             "changes": [change("Rejected", "BELOW_HARD_FLOOR")] * 6 + [change("Applied")] * 4}
        for n in analysis.analyze(s):
            self.assertTrue(insight.valid_wording(n["body"], n["facts"], n["body"]))
            self.assertFalse(insight.valid_wording(n["body"] + " Also 987654 more.", n["facts"], n["body"]))

    def test_findings_can_be_reworded_under_the_same_guard(self):
        n = analysis.refusals({"policy": {"hardMarginFloorPct": 5, "maxDiscountPct": 50},
                               "changes": [change("Rejected", "BELOW_HARD_FLOOR")] * 6 + [change("Applied")] * 4})[0]
        ok = insight.reword(n["kind"], n["refKey"], n["headline"], n["body"], n["facts"], wording=lambda s, u: "6 of 10 proposals hit the 5% floor.")
        self.assertEqual(ok["source"], "model")
        bad = insight.reword(n["kind"], n["refKey"], n["headline"], n["body"], n["facts"], wording=lambda s, u: "6 of 10 hit it; fix 77 products.")
        self.assertEqual(bad["source"], "template")


if __name__ == "__main__":
    unittest.main()

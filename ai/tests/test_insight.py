import json
import tempfile
import unittest

from missionai import insight, llm

SELL = {"product": "Squid Flakes Crackers", "branch": "Main", "daysLeft": 3, "batchQty": 27, "ratePerDay": 3.0, "unitsAtRisk": 18,
        "valueAtRiskAtCost": 270, "suggestedDiscountPct": 30, "suggestedPrice": 17.5, "proposalStatus": "Proposed"}
EXPIRED = {"product": "BIOGESIC", "branch": "Main", "daysLeft": -72, "batchQty": 90, "ratePerDay": 0, "unitsAtRisk": 90,
           "valueAtRiskAtCost": 3600, "suggestedDiscountPct": None, "suggestedPrice": None, "proposalStatus": None}


class Template(unittest.TestCase):
    def test_sell_fast_sentence_carries_the_numbers_and_the_discount(self):
        head, body = insight.template("SellFast", SELL)
        self.assertEqual(head, "Squid Flakes Crackers: 30% rush sale suggested")
        for part in ("27 units", "in 3 days", "about 3 a day", "about 18 will be left", "₱270 at cost", "30% rush sale at ₱17.50", "waiting for approval"):
            self.assertIn(part, body)

    def test_expired_stock_is_to_write_off_not_to_discount(self):
        head, body = insight.template("SellFast", EXPIRED)
        self.assertIn("write off", head)
        self.assertIn("expired 72 day(s) ago", body)
        self.assertNotIn("rush sale", body)

    def test_markdown_replenish_and_count_have_a_template_each(self):
        md = {"name": "Milk", "scope": "Main", "from": 60, "to": 48, "pct": -20, "marginNowPct": 40, "marginAfterPct": 25, "reason": "Expires soon."}
        self.assertIn("price down 20%", insight.template("Markdown", md)[0])
        rp = {"product": "Rice", "branch": "Main", "onHand": 10, "ratePerDay": 4, "daysOfCover": 2.5, "suggestedQty": 40, "leadTimeDays": 3}
        self.assertIn("40 units", insight.template("Replenish", rp)[1])
        ct = {"product": "Oil", "branch": "Main", "onHand": 50, "valueAtCost": 5000, "reason": "No receiving report."}
        self.assertIn("₱5,000", insight.template("Count", ct)[1])
        with self.assertRaises(ValueError):
            insight.template("Nope", {})


class Guard(unittest.TestCase):
    def test_wording_with_only_known_numbers_passes(self):
        text = "Of the 27 crackers expiring in 3 days, about 18 will be left, worth 270 pesos at cost. A 30% rush sale to 17.5 should clear them."
        self.assertTrue(insight.valid_wording(text, SELL))

    def test_an_invented_number_is_refused(self):
        self.assertFalse(insight.valid_wording("About 25 will be left, worth 270 pesos.", SELL))
        self.assertFalse(insight.valid_wording("Sell them at 45% off.", SELL))

    def test_empty_and_overlong_wording_is_refused(self):
        self.assertFalse(insight.valid_wording("", SELL))
        self.assertFalse(insight.valid_wording("word " * 200, SELL))


class Build(unittest.TestCase):
    def test_without_a_model_the_template_is_used(self):
        item = insight.build("SellFast", "SellFast:1", SELL)
        self.assertEqual(item["source"], "template")
        self.assertEqual(item["refKey"], "SellFast:1")

    def test_a_good_model_answer_is_used(self):
        good = "27 units expire in 3 days and about 18 will be left, worth ₱270 at cost; a 30% rush sale clears them."
        item = insight.build("SellFast", "SellFast:1", SELL, wording=lambda s, u: good)
        self.assertEqual(item["source"], "model")
        self.assertEqual(item["body"], good)

    def test_a_model_that_invents_a_number_falls_back(self):
        item = insight.build("SellFast", "SellFast:1", SELL, wording=lambda s, u: "About 99 will be left; sell at 50% off.")
        self.assertEqual(item["source"], "template")
        self.assertIn("₱270 at cost", item["body"])

    def test_a_model_that_fails_falls_back(self):
        def boom(s, u):
            raise TimeoutError("no answer")
        item = insight.build("SellFast", "SellFast:1", SELL, wording=boom)
        self.assertEqual(item["source"], "template")

    def test_the_model_only_gets_the_facts_and_the_sentence(self):
        seen = {}

        def spy(system, user):
            seen["system"], seen["user"] = system, json.loads(user)
            return None
        insight.build("SellFast", "SellFast:1", SELL, wording=spy)
        self.assertEqual(set(seen["user"]), {"facts", "sentence"})
        self.assertIn("never add", seen["system"].lower())

    def test_answers_are_cached_so_a_repeat_costs_nothing(self):
        calls = []
        good = "27 units expire in 3 days; about 18 will be left, worth ₱270 at cost."

        def counted(s, u):
            calls.append(1)
            return good
        with tempfile.TemporaryDirectory() as d:
            insight.build("SellFast", "a", SELL, wording=counted, cache_dir=d)
            again = insight.build("SellFast", "a", SELL, wording=counted, cache_dir=d)
        self.assertEqual(len(calls), 1)
        self.assertEqual(again["source"], "model")


class Provider(unittest.TestCase):
    def test_no_configuration_means_no_model(self):
        self.assertIsNone(llm.from_env({}))
        self.assertIn("standard wording", llm.describe({}))

    def test_each_provider_is_picked_from_its_variables(self):
        self.assertIn("Anthropic", llm.describe({"ANTHROPIC_API_KEY": "k"}))
        self.assertIn("vllm.local", llm.describe({"LLM_BASE_URL": "http://vllm.local:8000/v1", "LLM_MODEL": "qwen"}))
        self.assertIsNotNone(llm.from_env({"OPENAI_API_KEY": "k"}))


if __name__ == "__main__":
    unittest.main()

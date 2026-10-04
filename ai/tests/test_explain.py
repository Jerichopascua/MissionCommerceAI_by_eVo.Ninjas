import unittest
from unittest import mock

from missionai import explain
from missionai.demand import DemandModel
from missionai.optimizer import Batch, choose

POLICY = {"maxDiscountPct": 50, "hardMarginFloorPct": 5, "softMarginFloorPct": 15}


def decision(qty=60):
    return choose(Batch(1, 10, 100, "dairy", qty, 60, 100, 1, 12, name="Milk"), POLICY, DemandModel(prior_beta=-1.5))


class ExplainTests(unittest.TestCase):
    def test_template_mentions_discount_units_and_waste(self):
        text = explain.template(decision())
        self.assertIn("Milk", text)
        self.assertIn("% off", text)
        self.assertIn("pesos", text)
        self.assertIn("Prediction", text)

    def test_template_for_no_markdown(self):
        self.assertTrue(explain.template(decision(qty=4)).startswith("No markdown"))

    def test_template_explains_a_guardrail_refusal(self):
        text = explain.template(decision(), {"status": "refused", "code": "BELOW_HARD_FLOOR"})
        self.assertIn("hard margin floor", text)
        self.assertIn("BELOW_HARD_FLOOR", text)

    def test_pending_approval_is_stated(self):
        self.assertIn("waiting for approval", explain.template(decision(), {"status": "pending", "code": "APPROVAL_MODE"}))

    def test_no_endpoint_means_no_network_call(self):
        with mock.patch("urllib.request.urlopen") as op:
            explain.explain(decision(), None, endpoint=None)
        op.assert_not_called()

    def test_endpoint_failure_falls_back_to_the_template(self):
        d = decision()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertEqual(explain.explain(d, None, endpoint="http://x:8000"), explain.template(d))

    def test_endpoint_success_uses_the_model_sentence(self):
        class R:
            def read(self):
                return b'{"choices":[{"message":{"content":" Ok sentence. "}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        with mock.patch("urllib.request.urlopen", return_value=R()):
            self.assertEqual(explain.explain(decision(), None, endpoint="http://x:8000"), "Ok sentence.")


if __name__ == "__main__":
    unittest.main()

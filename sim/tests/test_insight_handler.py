import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))
from simpeso import agent_service                       # noqa: E402


class Acct:
    token = "t"


class FakeDriver:
    def __init__(self, status=200):
        self.posted = None
        self.status = status

    def count_suggestions(self, acct, status="Open", kind=None):
        if kind == "SellFast":
            return [{"id": 1, "product": "Squid Flakes", "branch": "Main", "daysLeft": 3, "batchQty": 27, "ratePerDay": 3.0, "unitsAtRisk": 18,
                     "valueAtRiskAtCost": 270, "suggestedDiscountPct": 30, "suggestedPrice": 17.5, "proposalStatus": "Proposed"},
                    {"id": 2, "product": "Biogesic", "branch": "Main", "daysLeft": -72, "batchQty": 90, "ratePerDay": 0, "unitsAtRisk": 90,
                     "valueAtRiskAtCost": 3600, "suggestedDiscountPct": None, "suggestedPrice": None, "proposalStatus": None}]
        return [{"id": 7, "product": "Oil", "branch": "Main", "onHand": 50, "valueAtCost": 5000, "reason": "No receiving report."}]

    def replenish_suggestions(self, acct, status="Open"):
        return [{"id": 9, "product": "Rice", "branch": "Main", "onHand": 10, "ratePerDay": 4, "daysOfCover": 2.5, "suggestedQty": 40, "leadTimeDays": 3}]

    def _call(self, method, path, token, json_body=None, raw=False, **kw):
        if method == "GET" and path.startswith("/api/Pricing/Approvals"):
            return {"items": [{"id": 5, "name": "Milk", "scope": "Main", "from": 60, "to": 48, "pct": -20, "marginNowPct": 40, "marginAfterPct": 25,
                               "reason": "Expires soon."}]}
        if method == "POST" and path == "/api/ai/insights":
            self.posted = json_body
            return (self.status, {"added": len(json_body["Items"]), "skipped": 0}) if raw else {"added": len(json_body["Items"])}
        raise AssertionError(path)


class InsightHandler(unittest.TestCase):
    def test_every_source_gets_a_note_and_nothing_else_is_called(self):
        drv = FakeDriver()
        text = agent_service.insight_handler(drv, Acct(), [1], wording=None)()
        kinds = [i["Kind"] for i in drv.posted["Items"]]
        self.assertEqual(sorted(kinds), ["Count", "Markdown", "Replenish", "SellFast", "SellFast"])
        self.assertIn("no language model connected", text)
        self.assertTrue(all(i["Source"] == "template" for i in drv.posted["Items"]))

    def test_nearest_expiry_first_and_expired_stock_is_to_write_off(self):
        drv = FakeDriver()
        agent_service.insight_handler(drv, Acct(), [1])()
        sell = [i for i in drv.posted["Items"] if i["Kind"] == "SellFast"]
        self.assertIn("write off", sell[0]["Headline"])             # -72 days sorts before 3 days
        self.assertIn("30% rush sale", sell[1]["Headline"])

    def test_a_model_that_invents_a_figure_is_not_used(self):
        drv = FakeDriver()
        text = agent_service.insight_handler(drv, Acct(), [1], wording=lambda s, u: "About 999 will be left.")()
        self.assertTrue(all(i["Source"] == "template" for i in drv.posted["Items"]))
        self.assertIn("0 reworded", text)

    def test_a_refusal_from_pesoweb_is_reported(self):
        with self.assertRaises(RuntimeError):
            agent_service.insight_handler(FakeDriver(status=422), Acct(), [1])()


if __name__ == "__main__":
    unittest.main()

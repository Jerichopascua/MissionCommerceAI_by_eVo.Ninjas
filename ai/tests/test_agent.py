import tempfile
import unittest
from pathlib import Path

from missionai.agent import MarkdownAgent
from missionai.demand import DemandModel
from missionai.recorder import PredictionRecorder

POLICY = {"configured": True, "autonomyMode": "Autonomous", "maxDiscountPct": 50, "hardMarginFloorPct": 5,
          "softMarginFloorPct": 15}


class FakeClient:
    def __init__(self, policy=POLICY, rows=None, reply=(200, {"decision": 0, "code": "OK", "priceChangeId": 1})):
        self._policy, self.rows, self.reply, self.posts = policy, rows if rows is not None else [row()], reply, []

    def policy(self):
        return self._policy

    def expiry_batches(self, wh):
        return self.rows

    def markdown(self, wh, pid, batch_id, new_price, reason, ref):
        self.posts.append({"wh": wh, "pid": pid, "batch": batch_id, "price": new_price, "ref": ref, "reason": reason})
        return self.reply


def row(batch=100, product=10, days=1, qty=60.0, cost=60.0, status="Critical"):
    return {"warehouseId": 1, "productId": product, "batchId": batch, "daysLeft": days, "qtyOnHand": qty, "unitCost": cost,
            "status": status}


INFO = {"category": "dairy", "list_price": 100.0, "discount_pct": 0, "name": "Milk"}


def make(client, rate=12.0):
    rec = PredictionRecorder(Path(tempfile.mkdtemp()) / "p.jsonl")
    return MarkdownAgent(client, DemandModel(prior_beta=-1.5), rec, lambda pid: INFO, lambda wh, pid: rate), rec


class AgentTests(unittest.TestCase):
    def test_off_mode_posts_nothing(self):
        c = FakeClient(policy={**POLICY, "autonomyMode": "Off"})
        agent, rec = make(c)
        self.assertEqual(agent.tick(6, [1])[0]["type"], "skip")
        self.assertEqual(c.posts, [])
        self.assertEqual(len(rec.items), 0)

    def test_unconfigured_policy_posts_nothing(self):
        c = FakeClient(policy={"configured": False, "autonomyMode": "Off"})
        agent, _ = make(c)
        agent.tick(6, [1])
        self.assertEqual(c.posts, [])

    def test_overstocked_batch_gets_a_markdown_with_prediction_ref(self):
        c = FakeClient()
        agent, rec = make(c)
        out = agent.tick(6, [1])
        self.assertEqual(len(c.posts), 1)
        self.assertEqual(out[0]["status"], "applied")
        self.assertEqual(c.posts[0]["ref"], out[0]["prediction"])
        self.assertIn(out[0]["prediction"], rec.items)
        self.assertLess(c.posts[0]["price"], 100)
        self.assertTrue(out[0]["explanation"])

    def test_unchanged_decision_posts_nothing_the_second_time(self):
        c = FakeClient()
        agent, _ = make(c)
        agent.tick(6, [1])
        agent.tick(7, [1])
        self.assertEqual(len(c.posts), 1)

    def test_one_prediction_per_batch(self):
        c = FakeClient()
        agent, rec = make(c)
        agent.tick(6, [1])
        agent.applied.clear()                       # force another post for the same batch
        agent.tick(7, [1])
        self.assertEqual(len(rec.items), 1)

    def test_pending_approval_stops_and_is_not_reproposed(self):
        c = FakeClient(reply=(202, {"decision": 1, "code": "APPROVAL_MODE", "priceChangeId": 77}))
        agent, _ = make(c)
        out = agent.tick(6, [1])
        self.assertEqual((out[0]["status"], out[0]["price_change_id"]), ("pending", 77))
        agent.tick(7, [1])
        self.assertEqual(len(c.posts), 1)

    def test_refusal_is_logged_with_its_code_and_not_retried_lower(self):
        c = FakeClient(reply=(422, {"decision": 2, "code": "BELOW_HARD_FLOOR", "message": "no"}))
        agent, _ = make(c)
        out = agent.tick(6, [1])
        self.assertEqual((out[0]["status"], out[0]["code"]), ("refused", "BELOW_HARD_FLOOR"))
        self.assertIn("BELOW_HARD_FLOOR", out[0]["explanation"])
        agent.tick(7, [1])
        self.assertEqual(len(c.posts), 1)

    def test_batches_that_are_not_at_risk_or_empty_are_ignored(self):
        c = FakeClient(rows=[row(status="Normal"), row(batch=101, qty=0), row(batch=102, days=9)])
        agent, _ = make(c)
        agent.tick(6, [1])
        self.assertEqual(c.posts, [])

    def test_lightly_stocked_batch_gets_no_markdown(self):
        c = FakeClient(rows=[row(qty=4)])
        agent, rec = make(c)
        agent.tick(6, [1])
        self.assertEqual(c.posts, [])
        self.assertEqual(len(rec.items), 0)

    def test_fefo_queue_is_respected_for_the_later_batch(self):
        c = FakeClient(rows=[row(batch=1, days=1, qty=30), row(batch=2, days=2, qty=30)])
        agent, _ = make(c, rate=12.0)
        agent.tick(6, [1])
        posted = {p["batch"] for p in c.posts}
        self.assertIn(1, posted)

    def test_unknown_product_or_rate_is_skipped(self):
        c = FakeClient()
        rec = PredictionRecorder(Path(tempfile.mkdtemp()) / "p.jsonl")
        agent = MarkdownAgent(c, DemandModel(), rec, lambda pid: None, lambda wh, pid: 5.0)
        agent.tick(6, [1])
        self.assertEqual(c.posts, [])
        agent2 = MarkdownAgent(c, DemandModel(), rec, lambda pid: INFO, lambda wh, pid: None)
        agent2.tick(6, [1])
        self.assertEqual(c.posts, [])


if __name__ == "__main__":
    unittest.main()

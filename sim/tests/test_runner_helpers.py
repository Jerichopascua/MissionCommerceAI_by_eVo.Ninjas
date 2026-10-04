import unittest

from simpeso import rng, runner, world, verticals
from simpeso.driver import Account, PesoWebDriver
from tests.test_driver import FakeResp, FakeSession


class RunnerHelperTests(unittest.TestCase):
    def test_expiry_products_get_two_staggered_batches_and_others_one_line(self):
        v = verticals.load_all()
        milk = next(p for p in verticals.build_catalog(v["convenience"], rng.derive(1), 30) if p.expiry)
        batches = runner._batches(milk, 40, rng.derive(1, "b"))
        self.assertEqual(len(batches), 2)
        self.assertEqual(sum(b["qty"] for b in batches), 40)
        self.assertLess(batches[0]["days"], batches[1]["days"])
        part = verticals.build_catalog(v["motorcycle_parts"], rng.derive(1), 5)[0]
        self.assertEqual(len(runner._batches(part, 40, rng.derive(1, "b"))), 1)

    def test_demand_estimate_is_deterministic_and_positive(self):
        plan = world.plan_group(21, "smoke")
        a = runner.estimate_demand(plan, 21)
        self.assertEqual(a, runner.estimate_demand(plan, 21))
        self.assertGreater(len(a), 10)
        self.assertTrue(all(q > 0 for q in a.values()))

    def test_tagging_keeps_emails_unique_per_run(self):
        self.assertEqual(runner._tagged("a@simworld.test", "r1"), "a.r1@simworld.test")

    def test_grant_branch_adds_the_warehouse_once_and_skips_when_present(self):
        detail = {"roleId": 1, "fullName": "O", "userName": "o", "email": "o@x", "phone": "", "defaultWarehouseId": 11,
                  "userWarehouses": [{"warehouseId": 11}]}
        sess = FakeSession([FakeResp(200, detail), FakeResp(200, detail), FakeResp(200, {})])
        d = PesoWebDriver("http://x", "r", session=sess)
        owner = Account("o@x", "pw", "tok", 1, 11, 5)
        d.grant_branch(owner, 12)
        put = sess.requests[-1]
        self.assertEqual(put[0], "PUT")
        self.assertEqual(put[2]["files"]["UserWarehouses[0].WarehouseId"], (None, "11"))
        self.assertEqual(put[2]["files"]["UserWarehouses[1].WarehouseId"], (None, "12"))
        self.assertNotIn("Subscription", put[2]["files"])           # an owner cannot change its own plan
        sess2 = FakeSession([FakeResp(200, detail)])
        PesoWebDriver("http://x", "r", session=sess2).grant_branch(owner, 11)
        self.assertEqual(len(sess2.requests), 1)                     # already assigned: no update call


if __name__ == "__main__":
    unittest.main()

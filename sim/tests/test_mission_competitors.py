import unittest

from simpeso import competitors, mission_sim, world
from missionai import missions as ms


class CompetitorFeedTests(unittest.TestCase):
    def test_the_same_world_always_has_the_same_rivals(self):
        a = competitors.prices_for(21, 7, 100.0)
        b = competitors.prices_for(21, 7, 100.0)
        self.assertEqual(a, b)
        self.assertNotEqual(a, competitors.prices_for(22, 7, 100.0))

    def test_every_rival_is_close_to_our_price_and_priced_in_pesos_ticks(self):
        for pid in range(1, 80):
            for row in competitors.prices_for(21, pid, 100.0):
                self.assertGreaterEqual(row["Price"], 85.0)
                self.assertLessEqual(row["Price"], 120.0)
                self.assertEqual(row["Price"], round(row["Price"]))
        cheap = competitors.prices_for(21, 3, 12.0)
        self.assertTrue(all(abs(r["Price"] * 2 - round(r["Price"] * 2)) < 1e-9 for r in cheap))          # half-peso ticks under 50

    def test_the_feed_has_one_row_per_rival_per_product_and_skips_unpriced_products(self):
        rows = competitors.feed(21, [{"id": 1, "price": 100.0}, {"id": 2, "price": 0}, {"id": 3, "price": 55.0}])
        self.assertEqual(len(rows), 2 * len(competitors.COMPETITORS))
        self.assertEqual({r["ProductId"] for r in rows}, {1, 3})


class FakeDriver:
    def __init__(self, status=200):
        self.status, self.posted = status, []

    def post_missions(self, acct, warehouse_ids, items):
        self.posted.append((warehouse_ids, items))
        return self.status, {"added": len(items)}


class Acct:
    token = "t"


def basket(hour, lines, value=100.0, perishable=False):
    return ms.Basket(hour, lines, float(lines), value, perishable)


class MissionHandlerTests(unittest.TestCase):
    def test_each_branch_s_picture_is_posted_with_its_warehouse_id(self):
        drv = FakeDriver()
        source = lambda: {7: [basket(18, 2)] * 12, 8: [basket(7, 1)] * 11}
        msg = mission_sim.mission_handler(drv, Acct(), [7, 8], source, 14)()
        warehouses, items = drv.posted[0]
        self.assertEqual(warehouses, [7, 8])
        self.assertEqual({i["WarehouseId"] for i in items}, {7, 8})
        self.assertTrue(all(i["WindowDays"] == 14 and i["Insight"] for i in items))
        self.assertIn("23 baskets at 2 branches", msg)

    def test_a_branch_with_too_few_baskets_is_left_out_and_the_message_says_so(self):
        drv = FakeDriver()
        msg = mission_sim.mission_handler(drv, Acct(), [7], lambda: {7: [basket(18, 2)] * 3})()
        self.assertEqual(drv.posted[0][1], [])
        self.assertIn("too few baskets", msg)

    def test_a_refusal_fails_the_run(self):
        with self.assertRaises(RuntimeError):
            mission_sim.mission_handler(FakeDriver(422), Acct(), [7], lambda: {7: [basket(18, 2)] * 12})()


class SimulatedBasketsTests(unittest.TestCase):
    def test_the_classifier_beats_guessing_on_simulated_shoppers_and_never_sees_their_mission(self):
        class Ctx:
            pass
        ctx = Ctx()
        ctx.state = {"seed": 21}
        ctx.plan = world.plan_group(21, "smoke")
        ctx.calib = None
        sim = mission_sim.sim_baskets(ctx, list(range(300, 306)))
        self.assertTrue(sim)
        result = mission_sim.score_sim(sim)
        self.assertGreater(result["baskets"], 100)
        kinds = len(result["by_truth"])
        self.assertGreater(result["agreement"], 1.5 / (len(ms.MISSIONS)))                                 # clearly better than picking at random
        self.assertGreaterEqual(kinds, 2)
        # the baskets handed to the classifier carry no mission field at all
        row = next(iter(sim.values()))[0][1]
        self.assertEqual(set(vars(row)), {"hour", "lines", "units", "value", "perishable"})


if __name__ == "__main__":
    unittest.main()

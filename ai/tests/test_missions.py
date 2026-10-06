import unittest

from missionai import missions as ms
from missionai.missions import Basket


def b(hour, lines, units=None, value=100.0, perishable=False):
    return Basket(hour, lines, units if units is not None else lines, value, perishable)


class ClassifyTests(unittest.TestCase):
    def test_a_big_basket_is_a_weekly_restock_at_any_hour(self):
        self.assertEqual(ms.classify(b(19, 9)), ms.WEEKLY_RESTOCK)
        self.assertEqual(ms.classify(b(3, 2, units=15)), ms.WEEKLY_RESTOCK)
        self.assertEqual(ms.classify(b(12, 4, value=900.0), median_value=200.0), ms.WEEKLY_RESTOCK)    # three times the usual value

    def test_value_alone_does_not_make_a_restock_of_a_one_item_basket(self):
        self.assertEqual(ms.classify(b(12, 1, value=900.0), median_value=100.0), ms.QUICK)

    def test_late_night_wins_over_the_other_time_rules(self):
        for h in (22, 23, 0, 3, 4):
            self.assertEqual(ms.classify(b(h, 2)), ms.LATE_NIGHT)
        self.assertNotEqual(ms.classify(b(5, 2)), ms.LATE_NIGHT)

    def test_morning_visits_are_small(self):
        self.assertEqual(ms.classify(b(7, 3)), ms.MORNING)
        self.assertNotEqual(ms.classify(b(7, 5)), ms.MORNING)

    def test_evening_baskets_with_fresh_food_are_a_dinner_run_otherwise_an_after_work_top_up(self):
        self.assertEqual(ms.classify(b(18, 4, perishable=True)), ms.DINNER)
        self.assertEqual(ms.classify(b(18, 4)), ms.AFTER_WORK)
        self.assertEqual(ms.classify(b(21, 6)), ms.AFTER_WORK)

    def test_one_or_two_items_at_other_times_is_a_quick_top_up_and_the_rest_is_everyday(self):
        self.assertEqual(ms.classify(b(13, 1)), ms.QUICK)
        self.assertEqual(ms.classify(b(13, 2)), ms.QUICK)
        self.assertEqual(ms.classify(b(13, 5)), ms.EVERYDAY)


class SummarizeTests(unittest.TestCase):
    def baskets(self):
        return [b(18, 2) for _ in range(6)] + [b(18, 4, perishable=True) for _ in range(3)] + [b(19, 2)] + [b(11, 9, value=800.0) for _ in range(2)]

    def test_shares_add_up_and_the_biggest_mission_is_first(self):
        rows = ms.summarize(self.baskets(), window_days=7)
        self.assertEqual(sum(r["baskets"] for r in rows), 12)
        self.assertAlmostEqual(sum(r["share_pct"] for r in rows), 100.0, places=1)
        self.assertEqual(rows[0]["baskets"], max(r["baskets"] for r in rows))
        self.assertTrue(all(r["window_days"] == 7 for r in rows))

    def test_the_busiest_hour_and_typical_basket_are_reported(self):
        rows = {r["mission"]: r for r in ms.summarize(self.baskets())}
        dinner = rows[ms.DINNER]
        self.assertEqual((dinner["baskets"], dinner["peak_hour"], dinner["avg_items"]), (3, 18, 4.0))
        self.assertIn("18:00", dinner["insight"])
        self.assertIn("mark down", dinner["insight"])

    def test_too_few_baskets_means_no_summary(self):
        self.assertEqual(ms.summarize([b(18, 2)] * 5), [])


class ScoreTests(unittest.TestCase):
    def test_a_prediction_counts_when_it_is_a_mission_the_truth_can_look_like(self):
        s = ms.score([("grab_and_go", ms.QUICK), ("grab_and_go", ms.MORNING), ("grab_and_go", ms.WEEKLY_RESTOCK), ("after_work_topup", ms.DINNER)])
        self.assertEqual(s["baskets"], 4)
        self.assertEqual(s["agreement"], 0.75)
        self.assertEqual(s["by_truth"]["grab_and_go"], {"baskets": 3, "agreement": 0.667})

    def test_no_pairs_gives_no_score(self):
        self.assertIsNone(ms.score([])["agreement"])


if __name__ == "__main__":
    unittest.main()

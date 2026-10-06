import unittest

from missionai import price_advisor as pa

POLICY = {"hardMarginFloorPct": 5, "softMarginFloorPct": 10}


def prod(cost=60, price=100, pid=1, cat="Grocery"):
    return {"id": pid, "name": f"P{pid}", "category": cat, "cost": cost, "price": price}


class AdviceTests(unittest.TestCase):
    def test_floor_price_is_cost_plus_hard_floor_rounded_up(self):
        self.assertEqual(pa.floor_price(60, 5), 63.0)
        self.assertEqual(pa.floor_price(74, 5), 78.0)           # 77.7 rounds up to the next whole peso
        self.assertEqual(pa.floor_price(10, 5), 10.5)

    def test_a_good_margin_item_with_low_sensitivity_is_raised_by_a_bounded_step(self):
        s = pa.advise_one(prod(60, 100), rate=10, beta=-1.2, beta_source="learned", policy=POLICY)
        self.assertEqual(s.status, "raise")
        self.assertLessEqual(s.change_pct, 10.0)
        self.assertGreater(s.profit_gain_per_day, 0)

    def test_the_step_is_bounded_even_when_the_unconstrained_optimum_is_far(self):
        s = pa.advise_one(prod(74, 77), rate=10, beta=-1.3, beta_source="assumed", policy=POLICY)
        self.assertLessEqual(abs(s.change_pct), 10.0)

    def test_no_regret_check_blocks_a_raise_that_loses_money_if_customers_are_more_sensitive(self):
        # near-elastic demand: a raise only pays if customers stay as assumed; with the stress scenario it must not be suggested
        s = pa.advise_one(prod(90, 100), rate=10, beta=-1.15, beta_source="assumed", policy=POLICY)
        self.assertGreaterEqual(s.profit_gain_if_more_sensitive, -pa.MIN_GAIN_SHARE * abs(s.profit_per_day_now) - 1e-6)

    def test_a_very_price_sensitive_product_is_held_or_lowered_never_raised(self):
        s = pa.advise_one(prod(60, 100), rate=10, beta=-4.0, beta_source="learned", policy=POLICY)
        self.assertIn(s.status, ("hold", "lower"))
        if s.status == "lower":
            self.assertGreaterEqual(s.suggested_price, s.floor_price)

    def test_never_suggests_below_the_margin_price(self):
        for beta in (-3.0, -5.0):
            s = pa.advise_one(prod(60, 66), rate=20, beta=beta, beta_source="learned", policy=POLICY)
            self.assertGreaterEqual(s.suggested_price, s.floor_price)

    def test_no_sales_evidence_gets_no_demand_based_suggestion(self):
        for rate in (None, 0):
            s = pa.advise_one(prod(), rate=rate, beta=-1.3, beta_source="assumed", policy=POLICY)
            self.assertEqual(s.status, "no_evidence")
            self.assertEqual(s.suggested_price, 100)

    def test_a_price_below_the_margin_price_is_a_margin_alert_with_the_floor_as_the_fix(self):
        s = pa.advise_one(prod(100, 101), rate=5, beta=-1.3, beta_source="assumed", policy=POLICY)
        self.assertEqual(s.status, "margin_alert")
        self.assertEqual(s.suggested_price, 105.0)

    def test_headroom_shows_how_far_a_markdown_can_go(self):
        s = pa.advise_one(prod(60, 100), rate=0, beta=-1.3, beta_source="assumed", policy=POLICY)
        self.assertAlmostEqual(s.headroom_pct, 37.0, places=1)          # 100 down to 63
        thin = pa.advise_one(prod(100, 106), rate=0, beta=-1.3, beta_source="assumed", policy=POLICY)   # floor 105, soft price 110
        self.assertLess(thin.headroom_pct, 1.0)
        self.assertIn("cannot be marked down", thin.reason)

    def test_reason_says_whether_the_sensitivity_was_learned_or_assumed(self):
        a = pa.advise_one(prod(), rate=10, beta=-1.2, beta_source="learned", policy=POLICY)
        b = pa.advise_one(prod(), rate=10, beta=-1.2, beta_source="assumed", policy=POLICY)
        if a.status in ("raise", "lower"):
            self.assertIn("learned", a.reason)
            self.assertIn("assumed", b.reason)

    def test_advise_covers_every_product_and_summarizes(self):
        products = [prod(60, 100, 1), prod(74, 82, 2), prod(100, 101, 3), prod(50, 80, 4)]
        out = pa.advise(products, {1: 10, 2: 10, 4: 6}, lambda c: (-1.3, "assumed"), POLICY)
        self.assertEqual([s.product_id for s in out], [1, 2, 3, 4])
        sm = pa.summarize(out)
        self.assertEqual(sm["products"], 4)
        self.assertEqual(sm["products_below_margin_price"], 1)
        self.assertEqual(sum(sm["by_status"].values()), 4)

    def test_summary_reports_a_conservative_gain_and_how_many_rest_on_an_assumption(self):
        products = [prod(60, 100, 1, "A"), prod(60, 100, 2, "B")]
        out = pa.advise(products, {1: 10, 2: 10}, lambda c: (-1.2, "learned") if c == "A" else (-1.2, "assumed"), POLICY)
        sm = pa.summarize(out)
        self.assertEqual((sm["suggestions_on_learned_sensitivity"], sm["suggestions_on_assumed_sensitivity"]), (1, 1))
        self.assertLess(sm["conservative_gain_per_day"], sm["expected_profit_gain_per_day"])

    def test_deterministic(self):
        a = pa.advise_one(prod(), rate=10, beta=-1.2, beta_source="learned", policy=POLICY)
        b = pa.advise_one(prod(), rate=10, beta=-1.2, beta_source="learned", policy=POLICY)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()


class CompetitorCapTests(unittest.TestCase):
    def test_a_raise_is_not_suggested_above_five_percent_over_the_lowest_rival(self):
        free = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY)
        capped = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY, competitor_low=101.0)
        self.assertEqual(free.status, "raise")
        self.assertLessEqual(capped.suggested_price, 101.0 * 1.05 + 1e-9)
        self.assertLess(capped.suggested_price, free.suggested_price)

    def test_a_rival_far_below_blocks_every_raise(self):
        s = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY, competitor_low=80.0)
        self.assertNotEqual(s.status, "raise")

    def test_the_cap_is_mentioned_when_it_held_a_raise_back(self):
        s = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY, competitor_low=104.0)
        self.assertEqual(s.status, "raise")
        self.assertIn("lowest competitor price", s.reason)

    def test_no_rival_means_no_cap_and_a_lower_price_is_never_blocked(self):
        a = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY)
        b = pa.advise_one(prod(60, 100), rate=10, beta=-1.0, beta_source="learned", policy=POLICY, competitor_low=None)
        self.assertEqual(a.suggested_price, b.suggested_price)
        low = pa.advise_one(prod(60, 100), rate=10, beta=-4.0, beta_source="learned", policy=POLICY, competitor_low=70.0)
        self.assertIn(low.status, ("lower", "hold"))

    def test_advise_passes_each_product_its_own_rival_price(self):
        out = pa.advise([prod(60, 100, pid=1), prod(60, 100, pid=2)], {1: 10, 2: 10}, lambda c: (-1.0, "learned"), POLICY, competitor_low={2: 80.0})
        self.assertEqual(out[0].status, "raise")
        self.assertNotEqual(out[1].status, "raise")

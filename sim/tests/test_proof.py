import unittest
from types import SimpleNamespace

from simpeso import proof, ai_hook


def arm(waste, margin, revenue=1000, units=100, applied=0, cal=None):
    m = {"waste_pesos": waste, "revenue": revenue, "margin": margin, "net": margin - waste, "units": units,
         "markdowns_applied": applied, "markdowns_refused": 0}
    if cal:
        m["calibration"] = cal
    return m


class SummaryTests(unittest.TestCase):
    def data(self):
        return {1: {"none": arm(100, 500), "fixed": arm(80, 480), "ai": arm(40, 520, applied=5)},
                2: {"none": arm(120, 450), "fixed": arm(90, 470), "ai": arm(70, 430, applied=6)}}

    def test_arm_means(self):
        s = proof.summarize(self.data())
        self.assertEqual(s["arms"]["none"]["waste_pesos"], 110)
        self.assertEqual(s["arms"]["ai"]["markdowns_applied"], 5.5)

    def test_paired_differences_and_win_counts(self):
        p = proof.summarize(self.data())["paired"]["ai_vs_none"]
        self.assertEqual(p["waste_pesos"]["mean_diff"], -55)           # lower waste is better
        self.assertEqual(p["waste_pesos"]["seeds_ai_better"], 2)
        self.assertEqual(p["margin"]["mean_diff"], 0)                  # +20 and -20
        self.assertEqual(p["margin"]["seeds_ai_better"], 1)
        self.assertEqual(p["net"]["seeds_ai_better"], 2)

    def test_ai_vs_fixed_is_reported_too(self):
        p = proof.summarize(self.data())["paired"]["ai_vs_fixed"]
        self.assertEqual(p["waste_pesos"]["mean_diff"], -30)
        self.assertEqual(p["waste_pesos"]["of"], 2)

    def test_calibration_is_pooled_when_present(self):
        d = self.data()
        d[1]["ai"]["calibration"] = {"resolved": 4, "interval_coverage": 0.5, "predicted_waste_pesos": 100, "realized_waste_pesos": 150,
                                      "units_mae": 2.0, "naive_units_mae": 3.0}
        d[2]["ai"]["calibration"] = {"resolved": 6, "interval_coverage": 0.9, "predicted_waste_pesos": 200, "realized_waste_pesos": 210,
                                      "units_mae": 1.0, "naive_units_mae": 3.0}
        c = proof.summarize(d)["calibration"]
        self.assertEqual((c["resolved"], c["predicted_waste_pesos"], c["realized_waste_pesos"]), (10, 300, 360))
        self.assertAlmostEqual(c["interval_coverage"], 0.7)

    def test_metrics_from_stats(self):
        m = proof.metrics_from({"revenue": 1000.0, "cogs": 600.0, "trial_waste_pesos": 150.0, "units": 40, "markdowns_applied": 3})
        self.assertEqual((m["margin"], m["net"], m["markdowns_refused"]), (400.0, 250.0, 0))

    def test_seed_parsing(self):
        self.assertEqual(proof.parse_seeds("1-3"), [1, 2, 3])
        self.assertEqual(proof.parse_seeds("4,9"), [4, 9])


class FakeDriver:
    def __init__(self, floor):
        self.floor, self.posts = floor, []

    def markdown(self, owner, wh, pid, batch, price, reason, ref, source):
        self.posts.append((batch, price, source))
        return (200, {}) if price >= self.floor else (422, {"code": "BELOW_HARD_FLOOR"})


class FixedRuleTests(unittest.TestCase):
    def make(self, floor):
        hooks = ai_hook.FixedRuleHooks.__new__(ai_hook.FixedRuleHooks)
        hooks.fixed_applied = hooks.fixed_refused = 0
        hooks._done = False
        hooks.lots = True
        hooks._catalog = {5: {"list_price": 100.0}}
        hooks.live_branches = lambda: [("c1", "c1-b1", 1)]
        hooks.batches = lambda owner, wh: [{"productId": 5, "batchId": 9, "daysLeft": 1, "qtyOnHand": 10},
                                           {"productId": 5, "batchId": 10, "daysLeft": 3, "qtyOnHand": 10}]
        hooks._refresh_ratios = lambda: None
        drv = FakeDriver(floor)
        ctx = SimpleNamespace(driver=drv, owner=lambda ckey: None)
        return hooks, ctx, drv

    def test_applies_30_percent_to_last_day_batches_only_and_as_manual(self):
        hooks, ctx, drv = self.make(floor=0)
        hooks.before_hour(ctx, 6)
        self.assertEqual(drv.posts, [(9, 70.0, "Manual")])
        self.assertEqual(hooks.fixed_applied, 1)

    def test_falls_back_when_guardrails_refuse(self):
        hooks, ctx, drv = self.make(floor=85)
        hooks.before_hour(ctx, 6)
        self.assertEqual([p[1] for p in drv.posts], [70.0, 80.0, 90.0])
        self.assertEqual(hooks.fixed_applied, 1)

    def test_counts_a_refusal_when_even_10_percent_is_refused(self):
        hooks, ctx, drv = self.make(floor=95)
        hooks.before_hour(ctx, 6)
        self.assertEqual((hooks.fixed_applied, hooks.fixed_refused), (0, 1))

    def test_rule_runs_once_per_day(self):
        hooks, ctx, drv = self.make(floor=0)
        hooks.before_hour(ctx, 6)
        hooks.before_hour(ctx, 7)
        self.assertEqual(len(drv.posts), 1)


if __name__ == "__main__":
    unittest.main()

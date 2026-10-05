import unittest

from simpeso import approver as ap, rng


def item(**kw):
    base = {"id": 1, "name": "Rice 5kg", "type": "Price", "lane": "Store manager", "confidence": "learned", "lowRisk": False,
            "belowSoftFloor": False, "pct": 3.0, "from": 100.0, "to": 103.0, "canApprove": True}
    base.update(kw)
    return base


class FakeDriver:
    def __init__(self, items, status=200, body=None):
        self.items, self.status, self.body, self.posts = items, status, body or {}, []

    def _call(self, method, path, token=None, json_body=None, raw=False, **kw):
        if method == "GET":
            return {"items": self.items}
        self.posts.append((path, json_body))
        return self.status, self.body


class Acct:
    token = "t"


class ApproverTests(unittest.TestCase):
    def test_low_risk_always_approved(self):
        for s in range(20):
            self.assertEqual(ap.decide(item(lowRisk=True), ap.ApproverStyle(), rng.derive(s, "x"))["action"], "approve")

    def test_a_cut_below_the_soft_floor_is_always_rejected(self):
        for s in range(20):
            self.assertEqual(ap.decide(item(belowSoftFloor=True, pct=-5.0, to=95.0), ap.ApproverStyle(), rng.derive(s, "x"))["action"], "reject")

    def test_a_raise_that_is_still_inside_the_soft_band_is_not_rejected_for_that(self):
        d = ap.decide(item(belowSoftFloor=True, confidence="rule", pct=10.0, to=110.0), ap.ApproverStyle(approve_rate_rule=1.0), rng.derive(1, "x"))
        self.assertEqual(d["action"], "approve")

    def test_assumed_evidence_is_approved_less_often_than_learned(self):
        st = ap.ApproverStyle()
        n = 400
        learned = sum(ap.decide(item(), st, rng.derive(s, "a"))["action"] != "reject" for s in range(n))
        assumed = sum(ap.decide(item(confidence="assumed"), st, rng.derive(s, "a"))["action"] != "reject" for s in range(n))
        self.assertGreater(learned, assumed + 100)

    def test_big_raise_is_trimmed_to_half_the_step(self):
        st = ap.ApproverStyle(approve_rate_learned=1.0)
        d = ap.decide(item(pct=12.0, to=112.0, lane="Pricing manager"), st, rng.derive(1, "x"))
        self.assertEqual((d["action"], d["new_price"]), ("edit", 106.0))

    def test_same_seed_same_decisions(self):
        a = [ap.decide(item(confidence="assumed"), ap.ApproverStyle(), rng.derive(7, "approver", i, 0))["action"] for i in range(30)]
        b = [ap.decide(item(confidence="assumed"), ap.ApproverStyle(), rng.derive(7, "approver", i, 0))["action"] for i in range(30)]
        self.assertEqual(a, b)

    def test_work_queue_posts_to_the_right_endpoints_and_skips_other_lanes(self):
        drv = FakeDriver([item(id=1, lowRisk=True), item(id=2, type="Markdown", lowRisk=True), item(id=3, canApprove=False),
                          item(id=4, belowSoftFloor=True, pct=-5.0, to=95.0)])
        out = ap.work_queue(drv, Acct(), seed=1)
        paths = [p for p, _ in drv.posts]
        self.assertEqual(paths, ["/api/Pricing/ApproveListPrice", "/api/Pricing/Approve", "/api/Pricing/RejectListPrice"])
        self.assertEqual((out["approved"], out["rejected"], out["failed"]), (2, 1, 0))

    def test_failed_calls_are_counted_not_hidden(self):
        out = ap.work_queue(FakeDriver([item(lowRisk=True)], status=409), Acct(), seed=1)
        self.assertEqual((out["approved"], out["failed"]), (0, 1))

    def test_a_proposal_gone_stale_is_counted_as_stale_not_failed(self):
        out = ap.work_queue(FakeDriver([item(lowRisk=True)], status=422, body={"code": "PRICE_CHANGED_SINCE"}), Acct(), seed=1)
        self.assertEqual((out["stale"], out["failed"]), (1, 0))

    def test_margin_fixes_are_nearly_always_approved_and_never_trimmed(self):
        st = ap.ApproverStyle()
        ds = [ap.decide(item(confidence="rule", pct=20.0, to=120.0, lane="Pricing manager"), st, rng.derive(s, "r")) for s in range(300)]
        self.assertGreater(sum(d["action"] == "approve" for d in ds), 280)
        self.assertEqual(sum(d["action"] == "edit" for d in ds), 0)


if __name__ == "__main__":
    unittest.main()

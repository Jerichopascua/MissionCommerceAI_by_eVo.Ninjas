import unittest

from simpeso import agent_service as ag


class Acct:
    token = "t"


class FakeDriver:
    """Plays PesoWeb's side of the run-request calls."""

    def __init__(self, enabled=True, requests=None, start_status=200):
        self.enabled = enabled
        self.requests = requests if requests is not None else [{"id": 7, "feature": "Pricing"}]
        self.start_status = start_status
        self.calls = []

    def _call(self, method, path, token=None, json_body=None, raw=False, **kw):
        self.calls.append((method, path, json_body))
        if path == "/api/ai/settings":
            return [{"key": "Pricing", "enabled": self.enabled}, {"key": "Replenish", "enabled": True}]
        if path.startswith("/api/ai/run-requests?"):
            return self.requests
        if path.endswith("/start"):
            return self.start_status, {}
        return 200, {}


def paths(drv):
    return [p for _, p, _ in drv.calls]


class AgentServiceTests(unittest.TestCase):
    def test_a_waiting_run_is_started_done_and_reported(self):
        drv = FakeDriver()
        out = ag.AgentRunner(drv, Acct(), {"Pricing": lambda: "proposed 3"}, log=lambda *_: None).poll_once()
        self.assertEqual(out[0]["outcome"], "done")
        self.assertIn("/api/ai/run-requests/7/start", paths(drv))
        finish = [b for _, p, b in drv.calls if p.endswith("/finish")][0]
        self.assertEqual((finish["Ok"], finish["Summary"]), (True, "proposed 3"))

    def test_a_switched_off_feature_is_never_run(self):
        ran = []
        drv = FakeDriver(enabled=False)
        out = ag.AgentRunner(drv, Acct(), {"Pricing": lambda: ran.append(1) or "x"}, log=lambda *_: None).poll_once()
        self.assertEqual(ran, [])
        self.assertIn("switched off", out[0]["outcome"])
        self.assertFalse(any(p.endswith("/finish") for p in paths(drv)))

    def test_a_handler_error_is_reported_as_failed_not_swallowed(self):
        def boom():
            raise ValueError("no model")
        drv = FakeDriver()
        out = ag.AgentRunner(drv, Acct(), {"Pricing": boom}, log=lambda *_: None).poll_once()
        self.assertEqual(out[0]["outcome"], "failed")
        finish = [b for _, p, b in drv.calls if p.endswith("/finish")][0]
        self.assertFalse(finish["Ok"])
        self.assertIn("no model", finish["Summary"])

    def test_a_feature_without_a_handler_fails_with_a_clear_message(self):
        drv = FakeDriver(requests=[{"id": 9, "feature": "Replenish"}])
        out = ag.AgentRunner(drv, Acct(), {}, log=lambda *_: None).poll_once()
        self.assertEqual(out[0]["outcome"], "failed")
        self.assertIn("no handler", out[0]["summary"])

    def test_a_run_someone_else_already_took_is_skipped(self):
        ran = []
        drv = FakeDriver(start_status=409)
        out = ag.AgentRunner(drv, Acct(), {"Pricing": lambda: ran.append(1) or "x"}, log=lambda *_: None).poll_once()
        self.assertEqual(ran, [])
        self.assertIn("could not start", out[0]["outcome"])

    def test_nothing_waiting_does_nothing(self):
        drv = FakeDriver(requests=[])
        self.assertEqual(ag.AgentRunner(drv, Acct(), {}, log=lambda *_: None).poll_once(), [])


if __name__ == "__main__":
    unittest.main()

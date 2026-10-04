import re
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "missionai"


class IndependenceTests(unittest.TestCase):
    def test_ai_never_touches_the_simulators_hidden_behavior(self):
        for path in PKG.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"simpeso|price_response|\.behavior|archetype", path.name)

    def test_the_llm_is_not_in_the_decision_path(self):
        for name in ("optimizer.py", "demand.py", "agent.py", "detectors.py", "recorder.py"):
            text = (PKG / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"urllib|requests|openai|vllm|chat/completions", name)

    def test_only_the_explainer_may_make_network_calls(self):
        callers = [p.name for p in PKG.glob("*.py") if re.search(r"urlopen|requests\.", p.read_text(encoding="utf-8"))]
        self.assertEqual(callers, ["explain.py"])


if __name__ == "__main__":
    unittest.main()

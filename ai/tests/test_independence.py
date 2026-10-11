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

    def test_only_the_wording_modules_may_make_network_calls(self):
        # explain.py (markdown notes) and llm.py (the client AI Insight uses to reword notes). Nothing that decides may reach the network.
        callers = [p.name for p in PKG.glob("*.py") if re.search(r"urlopen|requests\.", p.read_text(encoding="utf-8"))]
        self.assertEqual(sorted(callers), ["explain.py", "llm.py"])

    def test_no_decision_module_uses_the_wording_modules(self):
        wording = {"explain.py", "llm.py", "insight.py", "agent.py"}      # agent.py only asks explain.py to word a decision it already made
        for p in PKG.glob("*.py"):
            if p.name in wording or p.name == "__init__.py":
                continue
            self.assertNotRegex(p.read_text(encoding="utf-8"), r"import\s+(llm|insight|explain)|from\s+\.?\s*(llm|insight|explain)", p.name)


if __name__ == "__main__":
    unittest.main()

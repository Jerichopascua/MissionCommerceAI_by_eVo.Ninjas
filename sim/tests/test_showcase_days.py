import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import showcase_days as sd  # noqa: E402


def m(net, waste=0.0, margin=0.0, revenue=0.0, units=0.0):
    return {"net": net, "waste_pesos": waste, "margin": margin, "revenue": revenue, "units": units}


class ShowcaseDaysTests(unittest.TestCase):
    def test_parse_days(self):
        self.assertEqual(sd.parse_days("204-206"), [204, 205, 206])
        self.assertEqual(sd.parse_days("1,5"), [1, 5])

    def test_each_ai_day_is_paired_with_the_base_day_it_ran_beside(self):
        base = [m(-10), m(-20), m(-30), m(-40)]            # two days agent ON, then two days OFF
        on = [m(-5), m(-18)]
        off = [m(-31), m(-44)]
        s = sd.summarize(base, on, off)
        self.assertEqual(s["vs_base_agent_on"]["net"]["mean"], (5 + 2) / 2)
        self.assertEqual(s["vs_base_agent_off"]["net"]["mean"], (-1 - 4) / 2)
        self.assertEqual(s["vs_base_agent_on"]["net"]["days_better"], 2)
        self.assertEqual(s["vs_base_agent_off"]["net"]["days_better"], 0)

    def test_agent_adds_is_the_difference_of_the_two_settings(self):
        base = [m(0, 100), m(0, 100)]
        s = sd.summarize(base, [m(0, 60)], [m(0, 90)])
        self.assertEqual(s["agent_adds"]["waste_pesos"], (60 - 100) - (90 - 100))

    def test_less_waste_counts_as_better(self):
        s = sd.summarize([m(0, 100), m(0, 100)], [m(0, 80)], [m(0, 120)])
        self.assertEqual(s["vs_base_agent_on"]["waste_pesos"]["days_better"], 1)
        self.assertEqual(s["vs_base_agent_off"]["waste_pesos"]["days_better"], 0)


if __name__ == "__main__":
    unittest.main()

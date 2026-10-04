import unittest
from dataclasses import replace
from simpeso import archetypes, verticals


class ArchetypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = archetypes.customer_archetypes()
        cls.verts = verticals.load_all()

    def test_starter_library_size_and_validity(self):
        self.assertGreaterEqual(len(self.lib), 38)
        self.assertEqual(archetypes.validate_library(self.lib, self.verts), [])

    def test_every_vertical_has_missions_covered(self):
        for name, v in self.verts.items():
            fitting = [a for a in self.lib if name in a.verticals and any(m in v.missions for m in a.missions)]
            self.assertGreaterEqual(len(fitting), 6, name)

    def test_injected_duplicate_is_caught(self):
        dup = replace(self.lib[0], id="clone")
        problems = archetypes.validate_library(self.lib + [dup], self.verts)
        self.assertTrue(any("near-duplicate" in p for p in problems))

    def test_empty_grid_cell_is_caught(self):
        trimmed = [a for a in self.lib if not (a.income == "high" and a.time == "late_night")]
        problems = archetypes.validate_library(trimmed, self.verts)
        self.assertTrue(any("income=high time=late_night" in p for p in problems))

    def test_bad_mission_weights_are_caught(self):
        bad = replace(self.lib[0], missions={"grab_and_go": 0.3})
        problems = archetypes.validate_library([bad] + self.lib[1:], self.verts)
        self.assertTrue(any("do not sum to 1" in p for p in problems))

    def test_owner_library_has_a_conglomerate_and_known_verticals(self):
        owners = archetypes.owner_archetypes()
        self.assertTrue(any(o.conglomerate for o in owners))
        for o in owners:
            for v in o.verticals:
                self.assertIn(v, self.verts)
            self.assertGreaterEqual(o.ambition, 1)


if __name__ == "__main__":
    unittest.main()

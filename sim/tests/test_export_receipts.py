import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_receipts as ex       # noqa: E402

S = ex.SEP


class ExportTests(unittest.TestCase):
    def test_rows_become_csv_with_an_anonymous_receipt_id(self):
        raw = [f"1008{S}2026-04-28 22:01:18{S}443989260943{S}1.00{S}10.00{S}Drinks", f"1008{S}2026-04-28 22:01:18{S}555{S}2.00{S}5.50{S}NA", "(2 rows affected)", "", "Msg 123 something"]
        out = ex.to_csv_lines(raw, 6)
        self.assertEqual(out[0], "receipt_id,datetime,sku,qty,price,category")
        self.assertEqual(len(out), 3)
        first, second = out[1].split(","), out[2].split(",")
        self.assertEqual(first[0], second[0])                      # the same sale keeps one receipt id
        self.assertNotIn("1008", first[0])
        self.assertEqual(len(first[0]), 10)
        self.assertEqual(first[1], "2026-04-28 22:01:18")

    def test_the_id_depends_on_the_company_so_two_companies_never_collide(self):
        self.assertNotEqual(ex.receipt_id(6, "1"), ex.receipt_id(7, "1"))
        self.assertEqual(ex.receipt_id(6, "1"), ex.receipt_id(6, "1"))

    def test_quotes_in_names_cannot_break_the_file_and_the_export_feeds_the_loader(self):
        import tempfile
        from simpeso import replay
        raw = [f"1{S}2026-01-05 10:00:00{S}A\"B{S}1{S}9{S}Snacks, salty", f"2{S}2026-01-05 11:00:00{S}C{S}3{S}4{S}NA"]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.csv"
            path.write_text("\n".join(ex.to_csv_lines(raw, 6)) + "\n", encoding="utf-8")
            baskets = replay.load_store_pos(path)
            self.assertEqual(len(baskets), 2)
            self.assertEqual(sorted(b.hour for b in baskets), [10, 11])


if __name__ == "__main__":
    unittest.main()

"""Pre-data-preparation check: which real products will be treated as perishable, and which look perishable but are not.

    python scripts/check_perishables.py            # prints and writes sim/runs/perishables_review.txt (git-ignored)

Review this list before building a world with --perishables."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import perishables  # noqa: E402

BROAD = re.compile(r"MILK|YOGURT|CHEESE|BREAD|EGG|BUTTER|MARGARINE|HAM\b|BACON|SAUSAGE|CAKE|DONUT|SALAD|KIMCHI|NUGGET|CHICKEN|BEEF|PORK|FISH|SQUID|CREAM|JELLY|FRUIT|JUICE|TAPA|SISIG|YAKULT", re.I)


def main() -> int:
    items = json.loads((ROOT / "runs" / "real_catalog.json").read_text(encoding="utf-8"))["items"]
    chosen, near = [], []
    for i in items:
        rule = perishables.classify(i["name"])
        (chosen if rule else near if BROAD.search(i["name"]) else []).append((i, rule)) if (rule or BROAD.search(i["name"])) else None
    out = [f"{len(chosen)} of {len(items)} real products will be treated as perishable ({len(chosen) / len(items) * 100:.1f}%).", "",
           "CHOSEN (rule, shelf life in days, cost, price, margin over cost):"]
    for i, r in sorted(chosen, key=lambda x: (x[1].category, x[0]["name"])):
        out.append(f"  {r.category:28s} {str(r.shelf_life_days):10s} {i['name'][:44]:44s} cost {i['cost']:>6} price {i['price']:>6}  margin {(i['price'] - i['cost']) / i['cost'] * 100:4.0f}%")
    out += ["", f"LOOKED PERISHABLE BY A BROAD KEYWORD BUT NOT CHOSEN ({len(near)}), shelf-stable or non-food:"]
    out += [f"  {i['name'][:60]}" for i, _ in near]
    text = "\n".join(out)
    (ROOT / "runs" / "perishables_review.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

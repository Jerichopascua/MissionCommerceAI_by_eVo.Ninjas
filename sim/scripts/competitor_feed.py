"""Feed simulated competitor prices into a company in PesoWeb, so the Approval Center and the price advisor have rival prices to use.

    PESOWEB_ROOT_PASSWORD=... python scripts/competitor_feed.py --run real2 --company c1

The prices are the simulator's own assumption (see simpeso/competitors.py). In a real company they would be entered by a person, imported
from a file or fed by a price-monitoring service through the same endpoint: PUT /api/ai/competitor-prices (a person) or POST (an agent)."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import competitors, price_run, runner     # noqa: E402
from simpeso.driver import PesoWebDriver               # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--company", default="c1")
    ap.add_argument("--base-url", default="http://localhost:5071")
    args = ap.parse_args(argv)
    state = json.loads((runner.RUNS / args.run / "world.json").read_text(encoding="utf-8"))
    comp = state["companies"][args.company]
    wh = next(b["warehouse_id"] for b in comp["branches"].values() if "warehouse_id" in b)
    drv = PesoWebDriver(args.base_url, "competitor-feed")
    acct = drv.login(comp["owner"]["email"], comp["owner"]["password"])
    products = price_run.browse(drv, acct, wh)
    items = competitors.feed(state["seed"], products)
    saved = 0
    for i in range(0, len(items), 500):
        status, body = drv.post_competitor_prices(acct, items[i:i + 500])
        if status != 200:
            print("refused:", status, body)
            return 1
        saved += body.get("saved", 0)
    print(f"{len(products)} products, {saved} rival prices saved for {args.company} ({len(competitors.COMPETITORS)} rivals each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

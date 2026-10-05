"""Before the showcase run: do the PesoWeb prices of a world still equal the catalog it was built from, and what policy does each company run?

    python scripts/showcase_preflight.py --run real2
Read-only."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import ai_hook, price_run, runner     # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    args = ap.parse_args(argv)
    ns = argparse.Namespace(run=args.run, base_url=args.base_url, seed=21, profile="smoke", policy="off", calibration=None, calib_weight=0.5)
    ctx = runner._load(ns)
    hooks = ai_hook.AiHooks(ctx, agent_on=False)
    for ck in sorted(ctx.cmap):
        owner = ctx.owner(ck)
        whs = [b["warehouse_id"] for b in ctx.state["companies"][ck]["branches"].values() if "warehouse_id" in b]
        products = price_run.browse(ctx.driver, owner, whs[0])
        drift = []
        for p in products:
            info = hooks._catalog.get(p["id"])
            if info and abs(info["list_price"] - p["price"]) > 0.005:
                drift.append((info["name"], info["list_price"], p["price"]))
        pol = ctx.driver.pricing_policy(owner)
        pend = ctx.driver.list_price_changes(owner, status="PendingApproval")
        print(f"{ck}: {len(products)} products, price drift on {len(drift)}, policy {pol['autonomyMode']} hard {pol['hardMarginFloorPct']} soft {pol['softMarginFloorPct']} "
              f"auto-approve {pol['listPriceAutoApprove']}, pending list-price proposals {len(pend)}")
        for d in drift[:5]:
            print(f"     drift: {d[0][:34]:34s} catalog {d[1]:g} now {d[2]:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

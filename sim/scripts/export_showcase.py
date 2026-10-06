"""Turn the raw showcase outputs (sim/runs/showcase.json and showcase_days.json) into the small file the AI dashboard reads.

    python scripts/export_showcase.py            # writes results/showcase-real.json
Reads the real-catalog run; the product names and prices are the store's public shelf data."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import runner   # noqa: E402

OUT = ROOT.parent / "results" / "showcase-real.json"


def main() -> int:
    one = json.loads((runner.RUNS / "showcase.json").read_text(encoding="utf-8"))
    many = json.loads((runner.RUNS / "showcase_days.json").read_text(encoding="utf-8"))
    days = [{"day": d["day"], "agent_on": d["agent_on"],
             "base": {k: d["base"][k] for k in ("net", "margin", "waste_pesos", "revenue", "units")},
             "ai": {k: d["ai"][k] for k in ("net", "margin", "waste_pesos", "revenue", "units")}} for d in many["days"]]
    out = {
        "catalog": "Alma Store real catalog: 493 products with real cost and price, 21 perishables, 5 companies x 2 branches",
        "floors": one["floors"],
        "flow": one["pricing_flow"],
        "list_prices_changed": one["list_prices_changed"],
        "first_day": {"day": one["day"], "base": one["base"], "ai": one["ai"]},
        "summary": many["summary"],
        "days": days,
        "largest_changes": sorted(one["changes"], key=lambda c: -abs(c["pct"]))[:15],
        "checks": "An A/A run (same day in both worlds, no AI, no price change) shows zero difference over 5 days, after stock and lot sizes are equalised.",
        "caveats": ["Shopper price response is the simulator's own hidden assumption.",
                    "The markdown agent ran on different days than the agent-off setting, so their difference is an estimate.",
                    "One trial day is not a month of trading; there is no competitor price feed; the approver's waiting time is not simulated."],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(days)} days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

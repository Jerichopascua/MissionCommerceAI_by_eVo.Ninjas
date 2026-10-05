"""Concept proof, local only: one PesoWeb feature (FEFO expiry stock + guardrailed markdown pricing) and one very simple
agent task. Needs just the local PesoWeb server on PESOWEB_URL (default http://localhost:5071). No GPU, no LLM, no simulator.

    python demo/concept_demo.py

The story: a shop holds 40 units of milk that expire tomorrow next to 40 units that expire in 20 days, and sells about
12 a day. Left alone, roughly half of tomorrow's batch is thrown away. The agent reads PesoWeb's expiry feed, predicts
the outcome, proposes a markdown, and PesoWeb either applies it inside the shop's guardrails or refuses it. Every claim
is checked against what PesoWeb says back, not against the agent's own opinion."""
import datetime as dt
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "sim"), str(ROOT / "ai")]

from missionai.agent import MarkdownAgent          # noqa: E402
from missionai.demand import DemandModel           # noqa: E402
from missionai.recorder import PredictionRecorder  # noqa: E402
from simpeso.driver import PesoWebDriver           # noqa: E402
from simpeso.verticals import ProductSpec          # noqa: E402

BASE = os.environ.get("PESOWEB_URL", "http://localhost:5071")
COST, PRICE, LOT_QTY, DAILY_RATE = 60, 100, 40, 12
checks = []


def say(text=""):
    print(text, flush=True)


def check(ok: bool, what: str):
    checks.append(ok)
    say(f"   [{'PASS' if ok else 'FAIL'}] {what}")


class OwnerClient:
    """What the agent may use: this shop's own PesoWeb access."""

    def __init__(self, drv, acct):
        self.drv, self.acct = drv, acct

    def policy(self):
        return self.drv.pricing_policy(self.acct)

    def expiry_batches(self, wh):
        return self.drv.expiry_batches(self.acct, wh)

    def markdown(self, wh, pid, batch, price, reason, ref):
        return self.drv.markdown(self.acct, wh, pid, batch, price, reason, ref, "Ai")


def price_now(drv, acct, wh, cust, pid) -> float:
    """What a customer would pay right now: ring up one unit through the real POS."""
    sale = drv.sell(acct, wh, cust, [(pid, 1)], "Cash", PRICE)
    return float(sale["saleDetails"][0]["salePrice"])


def main() -> int:
    run = "concept-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    say(f"Local PesoWeb: {BASE}\n")

    say("1. A shop signs up and stocks milk (the shop owner uses the real PesoWeb API)")
    acct = drv.register("Concept Corner Store", "Demo", "Owner", f"{run}@concept.test", "Concept!123")
    wh = acct.warehouse_id
    basics = drv.setup_basics(acct)
    cat = drv.add_category(acct, "Dairy")
    sup = drv.add_supplier(acct, "Dairy Supplier", 1)
    spec = ProductSpec("MILK-1", "Fresh Milk 1L", "Dairy", COST, PRICE, True, (3, 7), 3)
    pid = drv.add_product(acct, spec, cat, basics)
    today = dt.date.today()
    drv.receive_stock(acct, wh, sup, [
        {"product_id": pid, "unit_cost": COST, "quantity": LOT_QTY, "batch_no": "LOT-TOMORROW",
         "expiry_date": (today + dt.timedelta(days=1)).isoformat(), "manufacturing_date": (today - dt.timedelta(days=2)).isoformat()},
        {"product_id": pid, "unit_cost": COST, "quantity": LOT_QTY, "batch_no": "LOT-LATER",
         "expiry_date": (today + dt.timedelta(days=20)).isoformat(), "manufacturing_date": today.isoformat()}], today.isoformat())
    cust = int(drv.customers(acct)[0]["id"])
    say(f"   {LOT_QTY} units expire tomorrow, {LOT_QTY} expire in 20 days. Cost {COST}, price {PRICE}. Normal sales: about {DAILY_RATE}/day.")

    say("\n2. The shop owner sets the rules PesoWeb will enforce (the agent cannot change them)")
    drv.set_pricing_policy(acct, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=6)
    pol = drv.pricing_policy(acct)
    say(f"   autonomy={pol['autonomyMode']}, never below cost + {pol['hardMarginFloorPct']}%, max discount {pol['maxDiscountPct']}%")

    say("\n3. Before the agent: what does a customer pay for the batch that expires tomorrow?")
    before = price_now(drv, acct, wh, cust, pid)
    say(f"   POS price: {before:.2f}   (FEFO sells tomorrow's batch first)")
    check(before == PRICE, f"price is the list price ({PRICE})")

    say("\n4. The agent task: 'decide what to do with stock that is about to expire'")
    rec = PredictionRecorder(Path(tempfile.mkdtemp()) / "predictions.jsonl")
    info = {"category": "Dairy", "list_price": PRICE, "discount_pct": 0, "name": "Fresh Milk 1L"}
    agent = MarkdownAgent(OwnerClient(drv, acct), DemandModel(prior_beta=-1.5), rec, lambda p: info, lambda w, p: DAILY_RATE)
    acts = agent.tick(6, [wh])
    act = next((a for a in acts if a.get("type") == "markdown"), None)
    if act:
        say(f"   agent: {act['explanation']}")
        say(f"   PesoWeb answered HTTP {act['http']} -> {act['status']}")
    check(bool(act) and act["status"] == "applied", "PesoWeb accepted the agent's markdown")
    check(bool(act) and act["new_price"] < PRICE and act["new_price"] >= COST * 1.05, "the new price is lower, but not below cost + 5%")

    say("\n5. After the agent: what does a customer pay now?")
    after = price_now(drv, acct, wh, cust, pid)
    say(f"   POS price: {after:.2f}   (was {before:.2f})")
    check(after < before, "the real POS now charges the marked-down price")

    say("\n6. The guardrail: someone (or something) asks for 80% off, far below cost")
    risk = [b for b in drv.expiry_batches(acct, wh) if b["batchNo"] == "LOT-TOMORROW"]
    status, body = drv.markdown(acct, wh, pid, risk[0]["batchId"], 20.0, "give it away", None, "Ai")
    say(f"   PesoWeb answered HTTP {status}: {body.get('code')} - {body.get('message')}")
    check(status == 422 and body.get("code") in ("EXCEEDS_MAX_DISCOUNT", "BELOW_HARD_FLOOR"), "PesoWeb refused it, with a reason")
    still = price_now(drv, acct, wh, cust, pid)
    check(still == after, "the refused price never reached the shelf")

    say("\n7. The audit trail inside PesoWeb")
    changes = drv._call("GET", f"/api/Pricing/Changes?warehouseId={wh}", acct.token)
    mine = [c for c in changes if c.get("source") == "Ai"]
    for c in mine[:3]:
        say(f"   price change #{c['id']}: {c['priceBefore']} -> {c['priceAfter']} ({c['status']}, {c.get('guardrailCode')}), prediction {c.get('predictionRef')}")
    check(any(c["status"] == "Applied" for c in mine), "the applied markdown is in PesoWeb's price-change ledger as an AI change")
    check(any(c["status"] != "Applied" for c in mine), "the refused attempt is in the ledger too")
    pred = list(rec.items.values())[0] if rec.items else None
    if pred:
        say(f"   recorded before acting: expected {pred['units']:.0f} units sold (range {pred['units_lo']:.0f} to {pred['units_hi']:.0f}),"
            f" about {pred['waste_pesos']:.0f} pesos wasted; without markdown {pred['baseline_waste_pesos']:.0f}")
    check(bool(pred) and pred["waste_pesos"] < pred["baseline_waste_pesos"], "the agent predicted less waste than doing nothing, and wrote it down first")

    passed = sum(checks)
    say(f"\nResult: {passed} of {len(checks)} checks passed.")
    say("Limits: the sales rate and price response are assumptions here (no sales history); the demo proves the mechanism and the guardrails, not a real-store lift.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Take the price advisor's suggestions through the guarded approval step in PesoWeb and verify the result.

    PESOWEB_ROOT_PASSWORD=... python scripts/apply_price_advice.py --run real2 --company c1 --propose 6 --approve 3 --reject 1

Steps: the AI proposes its top suggestions (source Ai, with a prediction reference); unsafe proposals show refusals; the owner
approves some, rejects one and leaves the rest pending; then it checks that approved prices changed in PesoWeb, a real sale is
charged the new price, refused and pending ones changed nothing, and the ledger holds every attempt.
--restore puts the approved products back to their original prices through the same approval step."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import runner                    # noqa: E402
from simpeso.driver import PesoWebDriver      # noqa: E402

checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def price_of(drv, acct, wh, pid):
    r = drv._call("GET", f"/api/Inventory/ProductDetail/{pid}?warehouse={wh}", acct.token)
    return float(r.get("price") or r["product"]["price"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--company", default="c1")
    ap.add_argument("--propose", type=int, default=6)
    ap.add_argument("--approve", type=int, default=3)
    ap.add_argument("--reject", type=int, default=1)
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--base-url", default="http://localhost:5071")
    args = ap.parse_args(argv)
    state = json.loads((runner.RUNS / args.run / "world.json").read_text(encoding="utf-8"))
    advice = json.loads((runner.RUNS / f"price-advice-{args.run}-{args.company}.json").read_text(encoding="utf-8"))
    c = state["companies"][args.company]
    drv = PesoWebDriver(args.base_url, "apply-advice")
    acct = drv.login(c["owner"]["email"], c["owner"]["password"])
    wh = next(b["warehouse_id"] for b in c["branches"].values() if "warehouse_id" in b)
    cust = int(drv.customers(acct)[0]["id"])
    acts = sorted((s for s in advice["suggestions"] if s["status"] in ("raise", "lower")), key=lambda s: -s["profit_gain_per_day"])[:args.propose]
    print(f"1. The AI proposes {len(acts)} list-price changes (company {args.company}, branch warehouse {wh})")
    proposals = []
    for s in acts:
        st, o = drv.propose_list_price(acct, wh, s["product_id"], s["suggested_price"], s["reason"], f"adv-{s['product_id']}", "Ai")
        proposals.append((s, o.get("priceChangeId")))
        print(f"   {s['name'][:34]:34s} {s['price']:>6g} -> {s['suggested_price']:>6g}  HTTP {st} {o.get('code')}")
        check(st == 202, f"{s['name'][:30]} waits for approval (202)")
    check(all(abs(price_of(drv, acct, wh, s["product_id"]) - s["price"]) < 0.005 for s, _ in proposals), "no price changed while the proposals are pending")

    print("2. Unsafe proposals are refused")
    big, low = acts[-1], acts[-2]
    st, o = drv.propose_list_price(acct, wh, big["product_id"], round(big["price"] * 1.4, 2), "too big a jump", "adv-unsafe", "Ai")
    print(f"   +40% on {big['name'][:30]}: HTTP {st} {o.get('code')}: {o.get('message')}")
    check(st == 422 and o.get("code") in ("EXCEEDS_MAX_INCREASE", "TOO_MANY_CHANGES"), "an oversized increase is refused with a reason")
    st, o = drv.propose_list_price(acct, wh, low["product_id"], round(low["cost"] * 0.9, 2), "below cost", "adv-unsafe2", "Ai")
    print(f"   below cost on {low['name'][:30]}: HTTP {st} {o.get('code')}")
    check(st == 422 and o.get("code") in ("BELOW_HARD_FLOOR", "EXCEEDS_MAX_DISCOUNT", "TOO_MANY_CHANGES"), "a price below cost is refused with a reason")

    print("3. The owner reviews: approve some, reject one, leave the rest pending")
    approved = proposals[:args.approve]
    rejected = proposals[args.approve:args.approve + args.reject]
    pending = proposals[args.approve + args.reject:]
    for s, pcid in approved:
        st, o = drv.approve_list_price(acct, pcid)
        print(f"   approve {s['name'][:34]:34s} HTTP {st} {o.get('code')} applied {o.get('appliedPrice')}")
        check(st == 200 and o.get("appliedPrice") == s["suggested_price"], f"{s['name'][:30]} approved and applied")
    for s, pcid in rejected:
        st, o = drv.reject_list_price(acct, pcid, "owner prefers to keep this price")
        check(st == 200, f"{s['name'][:30]} rejected by the owner")

    print("4. Verify in PesoWeb")
    for s, _ in approved:
        check(abs(price_of(drv, acct, wh, s["product_id"]) - s["suggested_price"]) < 0.005, f"{s['name'][:30]}: product price is now {s['suggested_price']:g}")
    for s, _ in rejected + pending:
        check(abs(price_of(drv, acct, wh, s["product_id"]) - s["price"]) < 0.005, f"{s['name'][:30]}: price unchanged ({s['price']:g})")
    if approved:
        s = approved[0][0]
        sale = drv.sell(acct, wh, cust, [(s["product_id"], 1)], "Cash", s["suggested_price"])
        paid = float(sale["saleDetails"][0]["salePrice"])
        print(f"   a real sale of {s['name'][:30]} is charged {paid:g}")
        check(abs(paid - s["suggested_price"]) < 0.005, "the POS charges the newly approved price")
    mine = [r for r in drv.list_price_changes(acct) if (r.get("predictionRef") or "").startswith("adv-")]
    states = {}
    for r in mine:
        states[r["status"]] = states.get(r["status"], 0) + 1
    print(f"   ledger rows from this run: {states}")
    check(states.get("Applied", 0) >= len(approved) and states.get("Rejected", 0) >= len(rejected) + 2 and states.get("PendingApproval", 0) >= len(pending),
          "the ledger holds every applied, rejected, refused and pending change")
    check(all(r["source"] == "Ai" for r in mine), "every row is marked as an AI proposal")

    if args.restore:
        print("5. Restore the approved products to their original prices through the same approval step")
        for s, _ in approved:
            st, o = drv.propose_list_price(acct, wh, s["product_id"], s["price"], "restore after the demo", "adv-restore", "Manual")
            if st == 202:
                drv.approve_list_price(acct, o["priceChangeId"])
            check(abs(price_of(drv, acct, wh, s["product_id"]) - s["price"]) < 0.005,
                  f"{s['name'][:30]}: restored to {s['price']:g}" if st == 202 else f"{s['name'][:30]}: restore refused ({o.get('code')})")
    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

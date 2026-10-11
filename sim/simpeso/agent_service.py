"""The agent runner: the small always-on program that connects the AI to one company's PesoWeb.

    python -m simpeso.agent_service --run real2 --company c1 --once        # handle what is waiting, then stop
    python -m simpeso.agent_service --run real2 --company c1 --interval 30 # keep polling every 30 seconds

It does what the owner's AI Control screen says, and nothing else:
  * reads the switches (GET /api/ai/settings): a feature that is off is never run;
  * picks up "run now" requests (GET /api/ai/run-requests), marks one running, does the work, reports Done or Failed.
PesoWeb enforces the switch on its side too (a switched-off AI Pricing gets its proposals refused), so a runner that
ignored the switch would still be stopped. Features with no handler here fail the run with a clear message.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def is_enabled(settings: list, feature: str) -> bool:
    row = next((s for s in settings if s["key"] == feature), None)
    return bool(row and row["enabled"])


class AgentRunner:
    def __init__(self, drv, acct, handlers: dict, log=print):
        self.drv, self.acct, self.handlers, self.log = drv, acct, handlers, log

    def settings(self) -> list:
        return self.drv._call("GET", "/api/ai/settings", self.acct.token)

    def poll_once(self) -> list:
        """Handle every waiting run request once. Returns one result row per request. Also asks PesoWeb to check the hub rules,
        so alerts open and close even when nobody has the Intelligence Hub open."""
        try:
            self.drv._call("POST", "/api/ai/hub/evaluate", self.acct.token, raw=True)
        except Exception:                   # a rules check that fails must not stop the runs
            pass
        settings = self.settings()
        waiting = self.drv._call("GET", "/api/ai/run-requests?status=Requested", self.acct.token) or []
        results = []
        for req in waiting:
            feature, rid = req["feature"], req["id"]
            if not is_enabled(settings, feature):
                # Starting a run for a switched-off feature makes PesoWeb cancel it and say so.
                self.drv._call("POST", f"/api/ai/run-requests/{rid}/start", self.acct.token, raw=True)
                results.append({"id": rid, "feature": feature, "outcome": "cancelled (switched off)"})
                self.log(f"run {rid} {feature}: switched off, not run")
                continue
            status, body = self.drv._call("POST", f"/api/ai/run-requests/{rid}/start", self.acct.token, raw=True)
            if status != 200:
                results.append({"id": rid, "feature": feature, "outcome": f"could not start ({status})"})
                continue
            handler = self.handlers.get(feature)
            try:
                if handler is None:
                    raise RuntimeError(f"this runner has no handler for {feature}")
                summary, ok = handler(), True
            except Exception as e:                      # report it to the owner instead of dying silently
                summary, ok = f"{type(e).__name__}: {e}", False
            self.drv._call("POST", f"/api/ai/run-requests/{rid}/finish", self.acct.token, json_body={"Ok": ok, "Summary": summary[:490]}, raw=True)
            results.append({"id": rid, "feature": feature, "outcome": "done" if ok else "failed", "summary": summary})
            self.log(f"run {rid} {feature}: {'done' if ok else 'FAILED'}: {summary}")
        return results

    def serve(self, interval: float, stop=lambda: False):
        while not stop():
            self.poll_once()
            time.sleep(interval)


SALES_PAGE = 5000
MIN_SPAN_DAYS = 3


def model_from_sales(drv, acct, warehouse_ids: list, window_days: int = 28, as_of=None) -> dict:
    """The sales model AI Pricing needs, built from a real company's own sales in PesoWeb (no simulator files): units sold per day for every
    product at every branch over the last `window_days` (ending today, or on `as_of`), counted from the first day the branch sold anything in
    that window. Price sensitivity is not learned from a real company yet: the model carries no observations, so the advisor uses the assumed
    slope and says "assumed". Returns {"rates": {"warehouse:product": units per day}, "observations": {}, "estimates": {}, "window": {...}}."""
    import datetime as dt
    end = as_of or dt.date.today()
    since = end - dt.timedelta(days=window_days)
    rates, spans = {}, {}
    for wh in warehouse_ids:
        rows, after = [], 0
        while True:
            page = drv.movements(acct, wh, "SALE_OUT", after, since.isoformat())
            rows += page
            if len(page) < SALES_PAGE:
                break
            after = max(m["id"] for m in page)
        rows = [m for m in rows if (m.get("transactionDate") or "")[:10] <= end.isoformat()]
        if not rows:
            continue
        first = min(dt.date.fromisoformat((m.get("transactionDate") or "")[:10]) for m in rows)
        span = max(MIN_SPAN_DAYS, min(window_days, (end - first).days + 1))
        spans[wh] = span
        for m in rows:
            key = f"{wh}:{m['productId']}"
            rates[key] = rates.get(key, 0.0) + float(m["qtyOut"]) / span
    return {"rates": rates, "observations": {}, "estimates": {}, "window": {"end": end.isoformat(), "days": window_days, "span_by_branch": spans}}


def pricing_handler(drv, acct, warehouse_ids: list, model, limit: int = 8, fix_limit: int = 25):
    """AI Pricing run: look at every product's cost, sales rate and learned price sensitivity, then put the best list-price changes
    into the Approval Center. Nothing is applied here; a person (or the tenant's own auto-approve limits) decides."""
    from . import price_run

    def run() -> str:
        m = model() if callable(model) else model          # a real company's model is rebuilt from its latest sales every run
        _, sugg, _ = price_run.suggestions_for(drv, acct, warehouse_ids, m)
        sent = price_run.propose_top(drv, acct, warehouse_ids[0], sugg, limit, fix_limit)
        waiting = sum(1 for r in sent if r["status"] == 202)
        applied = sum(1 for r in sent if r["status"] == 200)
        refused = sum(1 for r in sent if r["status"] == 422)
        fixes = sum(1 for r in sent if r["kind"] == "margin fix")
        return f"proposed {len(sent)} price changes ({fixes} margin fixes): {waiting} waiting in the Approval Center, {applied} auto-approved, {refused} refused by a rule"

    return run


BASELINE_DAYS_IN_MODEL = 2     # the saved model's sales rate is the average of the history phase's baseline days


def replenish_handler(drv, acct, warehouse_ids: list, model: dict = None, lead_days: int = 2, cover_days: int = 7, perishable_shelf_days: int = 5,
                      window_days: int = 14, as_of=None):
    """AI Replenish run: for every product at every branch, will the stock last until a delivery arrives? Posts the products that need an
    order to PesoWeb as suggestions (replacing the branch's earlier open ones). A person confirms; nothing is ordered here.

    Demand comes from the shop's own sales: the last `window_days` of sales when PesoWeb has dated sales, or, for a simulated world whose
    days all share one calendar date, the sales rate saved by its history phase (a Poisson spread is assumed, and the result is labelled limited)."""
    from . import price_run
    from missionai import replenish as rp
    import datetime as dt

    def daily_demand(wh):
        end = as_of or dt.date.today()
        since = (end - dt.timedelta(days=window_days)).isoformat()
        per = {}
        for m in drv.movements(acct, wh, "SALE_OUT", 0, since):
            day = (m.get("transactionDate") or "")[:10]
            if day > end.isoformat():
                continue
            per.setdefault(m["productId"], {}).setdefault(day, 0.0)
            per[m["productId"]][day] += float(m["qtyOut"])
        return lambda p: rp.demand_from_daily(list(per.get(p["id"], {}).values()) + [0.0] * max(0, window_days - len(per.get(p["id"], {})))) if p["id"] in per else None

    def run() -> str:
        items, urgent = [], 0
        for wh in warehouse_ids:
            products = price_run.browse(drv, acct, wh)
            if model:
                rates = model["rates"]
                demand = lambda p, wh=wh: (rp.demand_poisson(rates[f"{wh}:{p['id']}"], BASELINE_DAYS_IN_MODEL) if f"{wh}:{p['id']}" in rates else None)
                min_days = BASELINE_DAYS_IN_MODEL
            else:
                demand, min_days = daily_demand(wh), rp.MIN_DAYS_OF_DATA
            for s in rp.suggest_all(products, demand, lead_days=lead_days, cover_days=cover_days, min_days_of_data=min_days,
                                    shelf_life_for=lambda p: perishable_shelf_days if p.get("perishable") else None):
                urgent += 1 if s.urgent else 0
                items.append({"WarehouseId": wh, "ProductId": s.product_id, "OnHand": s.on_hand, "RatePerDay": s.rate_per_day, "DaysOfCover": s.days_of_cover,
                              "ReorderPoint": s.reorder_point, "SuggestedQty": s.suggested_qty, "UnitCost": s.unit_cost, "LeadTimeDays": s.lead_time_days,
                              "CoverDays": s.cover_days, "Confidence": s.confidence, "Reason": s.reason})
        status, body = drv.post_replenish(acct, warehouse_ids, items)
        if status != 200:
            raise RuntimeError(f"PesoWeb refused the suggestions: {status} {body}")
        return f"{body.get('added', 0)} reorder suggestions for {len(warehouse_ids)} branches ({urgent} urgent)"

    return run


COUNT_REASONS = {"delivered without a receiving report": "stock was delivered with no receiving report, so nothing can say how much really arrived",
                 "high-value fast mover": "a fast seller with a high value on the shelf: a small shortage costs the most here"}


HORIZON_DAYS = 14          # batches expiring within this many days are looked at
PROPOSE_WITHIN_DAYS = 3    # the nearest ones also get a markdown proposed (the same window the markdown agent uses)


def _batch_date(text):
    import datetime as dt
    return dt.date.fromisoformat(str(text)[:10]) if text else None


def expiry_findings(batches: list, info: dict, rates: dict, policy: dict, configured: bool, model, today, wh: int,
                    horizon_days: int = HORIZON_DAYS) -> list:
    """Which batches with an expiry date will not sell in time at the product's rate of sale, how much is at risk, and the discount (inside the
    owner's margin rules) that is expected to clear it. FEFO: units of the same product that expire sooner sell first. Returns dicts with
    batch_id, product_id, days_left, qty, rate, unsold, value, discount, new_price, reason, expired."""
    from missionai.optimizer import Batch, choose
    out, ahead = [], {}
    for b in sorted([x for x in batches if x.get("expiryDate") and float(x.get("qtyOnHand") or 0) > 0], key=lambda x: (x["productId"], str(x["expiryDate"]), x["id"])):
        pid, qty = b["productId"], float(b["qtyOnHand"])
        days_left = (_batch_date(b["expiryDate"]) - today).days
        queued = ahead.get(pid, 0.0)
        ahead[pid] = queued + qty
        p = info.get(pid)
        cost = float(b.get("cost") or (p or {}).get("cost") or 0)
        if days_left > horizon_days:
            continue
        name = (p or {}).get("name") or f"product {pid}"
        if days_left < 0:
            value = qty * cost
            out.append({"batch_id": b["id"], "product_id": pid, "days_left": days_left, "qty": qty, "rate": 0.0, "unsold": qty, "value": value,
                        "discount": 0.0, "new_price": None, "expired": True,
                        "reason": (f"Expired {-days_left} day(s) ago: {qty:g} unit(s), about ₱{value:,.0f} at cost, are still on the books. "
                                   f"They cannot be sold: write them off (Inventory, near-expiry monitoring).")})
            continue
        rate = float(rates.get(f"{wh}:{pid}", 0.0))
        days = max(1, days_left)
        expected = min(qty, max(0.0, rate * days - queued))
        unsold = qty - expected
        if unsold < 0.5:
            continue                                              # it should sell before it expires
        value = unsold * cost
        when = "today" if days_left == 0 else f"in {days_left} day(s)"
        base = f"{qty:g} unit(s) expire {when}. "
        discount, new_price, why = 0.0, None, ""
        if rate <= 0:
            base += "It has not sold in this period, so there is no evidence a discount would move it; consider a clearance price or moving it to a busier branch."
        else:
            base += f"At about {rate:.1f} a day only {expected:.0f} are expected to sell, so about {unsold:.0f} (₱{value:,.0f} at cost) may be thrown away."
            if not configured:
                why = " Set the pricing rules (Approval Center, Settings) so the AI can suggest a discount."
            elif p and p.get("price", 0) > 0 and cost > 0:
                batch = Batch(wh, pid, b["id"], p.get("category", ""), qty, cost, float(p["price"]), float(days), rate, 0.0, queued, name)
                d = choose(batch, policy, model, 6)
                if d.discount_pct > 0:
                    discount, new_price = d.discount_pct, d.new_price
                    why = (f" A {discount:g}% markdown (to ₱{new_price:,.0f}) is expected to sell {d.mean_units:.0f} of the {qty:g}"
                           f" and cut the waste from about ₱{d.baseline_waste_pesos:,.0f} to ₱{d.waste_pesos:,.0f}.")
                else:
                    why = " No discount inside your margin rules is expected to sell it in time."
        out.append({"batch_id": b["id"], "product_id": pid, "days_left": days_left, "qty": qty, "rate": rate, "unsold": unsold, "value": value,
                    "discount": discount, "new_price": new_price, "expired": False, "reason": base + why})
    return out


def loss_prevention_handler(drv, acct, warehouse_ids: list, per_branch: int = 8, window_days: int = 28, as_of=None,
                            horizon_days: int = HORIZON_DAYS, propose_markdowns: bool = True, today=None):
    """AI Product Loss Prevention run: PesoWeb's POS cannot see a short delivery or silent stock loss, so the AI spends a small counting budget
    where a loss would cost the most and is least likely to be explained by a record. It ranks stock delivered without a receiving report first,
    then high-value fast sellers, and posts the top few per branch as "count first" suggestions. Nothing is counted or changed here.

    It also covers the other kind of loss, stock that expires unsold: for every batch with an expiry date inside `horizon_days` it works out how
    much will not sell in time at the product's rate of sale, what that is worth at cost and the discount that would clear it, and posts it as a
    "sell fast" suggestion. For batches 1 to 3 days from expiry it also PROPOSES that markdown (source AI): PesoWeb's guardrails, the company's
    autonomy mode and the branch's AI-markdown switch decide whether it waits for a person, applies, or is refused."""
    from . import price_run
    from missionai import detectors
    import datetime as dt

    def run() -> str:
        end = as_of or dt.date.today()
        since = (end - dt.timedelta(days=window_days)).isoformat()
        receipts, sales, costs, on_hand, info_by_wh = [], {}, {}, {}, {}
        for wh in warehouse_ids:
            receipts += drv.all_receipts(acct, wh)
            after = 0
            while True:
                page = drv.movements(acct, wh, "SALE_OUT", after, since)
                for m in page:
                    if (m.get("transactionDate") or "")[:10] <= end.isoformat():
                        sales[(wh, m["productId"])] = sales.get((wh, m["productId"]), 0.0) + float(m["qtyOut"])
                if len(page) < SALES_PAGE:
                    break
                after = max(m["id"] for m in page)
            for p in price_run.browse(drv, acct, wh):
                on_hand[(wh, p["id"])] = p["stock"]
                info_by_wh.setdefault(wh, {})[p["id"]] = p
                if p["cost"] > 0 and p["stock"] > 0:          # nothing on the shelf at this branch: nothing to count there
                    costs[(wh, p["id"])] = p["cost"]
        ranked = detectors.rank_count_targets(receipts, sales, costs, per_branch * 3)       # a few extra: some have nothing on the shelf any more
        targets, taken = [], {}
        for tg in ranked:
            if on_hand.get((tg.warehouse_id, tg.product_id), 0) <= 0 or taken.get(tg.warehouse_id, 0) >= per_branch:
                continue
            taken[tg.warehouse_id] = taken.get(tg.warehouse_id, 0) + 1
            targets.append(tg)
        items = []
        for tg in targets:
            sold = sales.get((tg.warehouse_id, tg.product_id), 0.0)
            why = "; ".join(("a lot of value on the shelf for a product that has not sold in this period" if (r == "high-value fast mover" and sold <= 0)
                             else COUNT_REASONS.get(r, r)) for r in tg.reasons) or "worth a count"
            items.append({"WarehouseId": tg.warehouse_id, "ProductId": tg.product_id, "Score": round(tg.score, 2), "Reason": why[:380].capitalize() + "."})
        # ---- the expiry side: what will not sell before it expires, and what to do about it
        sell_items, proposed, at_risk_value = [], 0, 0.0
        batches_by_wh = {wh: drv.all_batches(acct, wh) for wh in warehouse_ids}
        if any(batches_by_wh.values()):
            pol = drv.pricing_policy(acct) or {}
            configured = bool(pol.get("configured", True)) and str(pol.get("autonomyMode", "Off")).lower() != "off"
            policy = {"maxDiscountPct": float(pol.get("maxDiscountPct") or 0), "hardMarginFloorPct": float(pol.get("hardMarginFloorPct") or 0),
                      "softMarginFloorPct": float(pol.get("softMarginFloorPct") or 0)}
            rates = model_from_sales(drv, acct, warehouse_ids, window_days, as_of)["rates"]
            dm = price_run.demand_model({"observations": {}, "estimates": {}})
            now = today or dt.date.today()
            earlier = {}
            for s in drv.count_suggestions(acct, "Open", "SellFast"):
                if s.get("batchId") and s.get("proposalStatus"):
                    earlier[(s["warehouseId"], s["batchId"])] = s["proposalStatus"]
            for wh in warehouse_ids:
                for f in expiry_findings(batches_by_wh[wh], info_by_wh.get(wh, {}), rates, policy, configured, dm, now, wh, horizon_days):
                    status_text = earlier.get((wh, f["batch_id"]))
                    if (propose_markdowns and configured and not f["expired"] and f["discount"] > 0 and 1 <= f["days_left"] <= PROPOSE_WITHIN_DAYS
                            and status_text is None):
                        st, body = drv.markdown(acct, wh, f["product_id"], f["batch_id"], f["new_price"], f["reason"][:280], None, "Ai")
                        code = (body or {}).get("code") or (body or {}).get("Code")
                        status_text = "Applied" if st == 200 else "Proposed" if st == 202 else f"Refused: {code or st}"
                        proposed += 1 if st in (200, 202) else 0
                    at_risk_value += f["value"]
                    sell_items.append({"WarehouseId": wh, "ProductId": f["product_id"], "Kind": "SellFast", "BatchId": f["batch_id"],
                                       "ExpiryDate": (now + dt.timedelta(days=f["days_left"])).isoformat(), "DaysLeft": f["days_left"],
                                       "BatchQty": f["qty"], "RatePerDay": round(f["rate"], 3), "UnitsAtRisk": round(f["unsold"], 2),
                                       "ValueAtRisk": round(f["value"], 2), "SuggestedDiscountPct": f["discount"] or None, "SuggestedPrice": f["new_price"],
                                       "ProposalStatus": status_text, "Score": max(1.0, round(f["value"], 2)) * (2 if f["expired"] else 1),
                                       "Reason": f["reason"][:395]})
        items += sell_items
        status, body = drv.post_count_suggestions(acct, warehouse_ids, items)
        if status != 200:
            raise RuntimeError(f"PesoWeb refused the count suggestions: {status} {body}")
        unreported = sum(1 for tg in targets if "delivered without a receiving report" in tg.reasons)
        n_count = len([i for i in items if i.get("Kind") != "SellFast"])
        text = (f"{n_count} products to count first at {len(warehouse_ids)} branch(es) ({unreported} with an unreported delivery)"
                f"; {len(sell_items)} batch(es) may expire unsold (about ₱{at_risk_value:,.0f} at cost), {proposed} markdown(s) proposed")
        if body.get("skipped"):
            text += f"; {body.get('skipped', 0)} left out (already handled lately)"
        return text

    return run


def _wording():
    """The language model for AI Insight, from the environment (see missionai.llm), or None for standard wording."""
    from missionai import llm
    return llm.from_env()


def _insight_cache():
    from pathlib import Path
    return str(Path(__file__).resolve().parent.parent / "runs" / "insight-cache")


def insight_handler(drv, acct, warehouse_ids: list, wording=None, cache_dir=None, per_kind: int = 12):
    """AI Insight run: plain-language notes on what the other AI features suggested and why. It reads what PesoWeb holds (batches that may expire
    unsold, price changes waiting for approval, what to count first, what to reorder), builds a standard sentence for each from the numbers, and
    posts them for the Intelligent Hub. A language model (`wording`, when one is connected) may only reword a sentence, and a figure it adds is
    thrown away (see missionai.insight). Nothing here decides or changes anything."""
    from missionai import insight as ins

    def run():
        notes, plan = [], []
        sell = [r for r in drv.count_suggestions(acct, "Open", "SellFast") or []]
        sell.sort(key=lambda r: (r.get("daysLeft") if r.get("daysLeft") is not None else 99, -(r.get("valueAtRiskAtCost") or 0)))
        for r in sell[:per_kind]:
            plan.append(("SellFast", f"SellFast:{r['id']}", {k: r.get(k) for k in (
                "product", "branch", "daysLeft", "batchQty", "ratePerDay", "unitsAtRisk", "valueAtRiskAtCost", "suggestedDiscountPct",
                "suggestedPrice", "proposalStatus")}))
        queue = drv._call("GET", "/api/Pricing/Approvals", acct.token) or {}
        for r in (queue.get("items") or [])[:per_kind]:
            plan.append(("Markdown", f"Markdown:{r['id']}", {k: r.get(k) for k in (
                "name", "scope", "from", "to", "pct", "marginNowPct", "marginAfterPct", "reason")}))
        count = [r for r in drv.count_suggestions(acct, "Open", "Count") or []]
        for r in count[:max(3, per_kind // 3)]:
            plan.append(("Count", f"Count:{r['id']}", {k: r.get(k) for k in ("product", "branch", "onHand", "valueAtCost", "reason")}))
        for r in (drv.replenish_suggestions(acct, "Open") or [])[:max(3, per_kind // 3)]:
            plan.append(("Replenish", f"Replenish:{r['id']}", {k: r.get(k) for k in (
                "product", "branch", "onHand", "ratePerDay", "daysOfCover", "suggestedQty", "leadTimeDays")}))
        for kind, ref, facts in plan:
            try:
                notes.append(ins.build(kind, ref, facts, wording=wording, cache_dir=cache_dir))
            except (KeyError, TypeError, ValueError):
                continue                    # a row missing a fact is left out rather than guessed
        status, body = drv._call("POST", "/api/ai/insights", acct.token,
                                 json_body={"Items": [{"Kind": n["kind"], "RefKey": n["refKey"], "Headline": n["headline"], "Body": n["body"],
                                                       "Source": n["source"]} for n in notes]}, raw=True)
        if status != 200:
            raise RuntimeError(f"PesoWeb refused the insights: {status} {body}")
        reworded = sum(1 for n in notes if n["source"] == "model")
        text = f"{len(notes)} plain-language note(s): {reworded} reworded by the language model, {len(notes) - reworded} in standard wording"
        if wording is None:
            text += " (no language model connected)"
        return text

    return run


def monitoring_handler(drv, acct, warehouse_ids: list, today=None, history_days: int = 28, event_pages: int = 20):
    """AI Monitoring: asks PesoWeb to check the company's rules, then compares each branch with its own recent past and posts
    everything unusual as findings (alerts follow the "Unusual activity found by AI" rule). The scan is complete each time, so findings
    that no longer apply close."""
    def run() -> str:
        import datetime as dt
        from missionai import monitor
        day = today() if callable(today) else (today or dt.date.today())
        drv._call("POST", "/api/ai/hub/evaluate", acct.token, raw=True)
        names = drv.branch_names(acct)
        since = (day - dt.timedelta(days=history_days)).isoformat()
        daily = {}
        for wh in warehouse_ids:
            rows, after = [], 0
            while True:
                page = drv.baskets(acct, wh, after, since)
                got = page.get("baskets", [])
                rows += got
                if len(got) < 2000:
                    break
                after = page["nextAfterId"]
            daily[wh] = monitor.daily_totals(rows)
        events, after = [], 0
        for _ in range(event_pages):
            page = drv.events(acct, after)
            got = page.get("events", [])
            events += got
            if len(got) < 1000:
                break
            after = page["nextAfterId"]
        findings = monitor.all_findings(names, day, daily, drv.cash_shifts(acct), events, drv.ledger_drift(acct))
        status, body = drv.post_monitor_findings(acct, findings)
        if status != 200:
            raise RuntimeError(f"PesoWeb refused the findings ({status}): {body}")
        shown = ", ".join(sorted({f["kind"] for f in findings})) or "nothing unusual"
        return (f"checked the rules and {len(warehouse_ids)} branch(es) against their own recent past: {len(findings)} unusual ({shown}); "
                f"{body.get('opened', 0)} new, {body.get('updated', 0)} still open, {body.get('closed', 0)} closed")
    return run


def serve_real(args) -> int:
    """The agent runner for a real company: no world.json, no model.json, no simulator."""
    import datetime as dt
    import getpass
    from . import mission_sim
    from .driver import PesoWebDriver
    if not args.email:
        print("--real needs --email <the company owner's login>", file=sys.stderr)
        return 2
    password = os.environ.get("PESOWEB_AGENT_PASSWORD") or (getpass.getpass("Password for " + args.email + ": ") if sys.stdin.isatty() else None)
    if not password:
        print("set PESOWEB_AGENT_PASSWORD in this window (it is never saved or printed)", file=sys.stderr)
        return 2
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    drv = PesoWebDriver(args.base_url, "agent-real")
    acct = drv.login(args.email, password)
    branches = drv._call("GET", "/api/ai/branch-settings", acct.token) or []
    whs = [b["warehouseId"] for b in branches]
    if not whs:
        print("that company has no branches", file=sys.stderr)
        return 1
    model = lambda: model_from_sales(drv, acct, whs, args.history_days, as_of)           # noqa: E731
    handlers = {"Pricing": pricing_handler(drv, acct, whs, model, args.limit),
                "Replenish": replenish_handler(drv, acct, whs, None, window_days=args.history_days, as_of=as_of),
                "CustomerMission": mission_sim.mission_handler(drv, acct, whs, lambda: mission_sim.pesoweb_baskets(drv, acct, whs, args.history_days, as_of), args.history_days),
                "Monitoring": monitoring_handler(drv, acct, whs, today=as_of),
                "LossPrevention": loss_prevention_handler(drv, acct, whs, window_days=args.history_days, as_of=as_of),
                "Insight": insight_handler(drv, acct, whs, wording=_wording(), cache_dir=_insight_cache())}
    agent = AgentRunner(drv, acct, handlers)
    window = f"the {args.history_days} days to {as_of.isoformat()}" if as_of else f"the last {args.history_days} days"
    print(f"REAL company {args.email}: {len(whs)} branch(es), looking at {window}.")
    print("Pricing proposals go to the Approval Center; nothing changes a price or an order without a person or the company's own limits.")
    if args.once:
        agent.poll_once()
        return 0
    print(f"polling every {args.interval:g}s for Run now requests; Ctrl+C to stop")
    try:
        agent.serve(args.interval)
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None) -> int:
    from . import runner
    from .driver import PesoWebDriver
    ap = argparse.ArgumentParser(prog="simpeso.agent_service")
    ap.add_argument("--run", default=None, help="a simulated world under sim/runs (gives the company logins and the learned model)")
    ap.add_argument("--company", default="c1")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--limit", type=int, default=8, help="most price proposals per Pricing run")
    ap.add_argument("--mission-source", choices=["sim", "pesoweb"], default="sim",
                    help="where AI Customer Mission gets baskets: the simulator's visits (a simulated world's sales carry no time of day) or PesoWeb's sales")
    ap.add_argument("--real", action="store_true",
                    help="serve a REAL company: log in with --email (the password from PESOWEB_AGENT_PASSWORD, or asked for), build the sales model from its own "
                         "PesoWeb sales, read baskets from its sales. No simulated world is used. Everything the AI proposes still goes through PesoWeb's rules and approvals.")
    ap.add_argument("--email", default=None, help="with --real: the company owner's login")
    ap.add_argument("--history-days", type=int, default=28, help="with --real: how many days of sales the AI looks at")
    ap.add_argument("--as-of", default=None, help="with --real: end the look-back on this date (YYYY-MM-DD) instead of today, for a company whose last sales are older")
    args = ap.parse_args(argv)
    if args.real:
        return serve_real(args)
    if not args.run:
        print("give --run <simulated world>, or --real --email <login> for a real company", file=sys.stderr)
        return 2
    run_dir = runner.RUNS / args.run
    state = json.loads((run_dir / "world.json").read_text(encoding="utf-8"))
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    comp = state["companies"][args.company]
    drv = PesoWebDriver(args.base_url, "agent-service")
    acct = drv.login(comp["owner"]["email"], comp["owner"]["password"])
    whs = [b["warehouse_id"] for b in comp["branches"].values() if "warehouse_id" in b]
    from . import mission_sim

    def mission_source():
        if args.mission_source == "pesoweb":
            return mission_sim.pesoweb_baskets(drv, acct, whs)
        import argparse as _ap
        ctx = runner._load(_ap.Namespace(run=args.run, base_url=args.base_url, seed=21, profile="smoke", policy="off", calibration=None, calib_weight=0.5))
        sim = mission_sim.sim_baskets(ctx, list(range(300, 314)))
        by_wh = {}
        for (ck, bk), rows in sim.items():
            if ck == args.company:
                by_wh[comp["branches"][bk]["warehouse_id"]] = [b for _, b in rows]
        return by_wh

    agent = AgentRunner(drv, acct, {"Pricing": pricing_handler(drv, acct, whs, model, args.limit), "Replenish": replenish_handler(drv, acct, whs, model),
                                    "CustomerMission": mission_sim.mission_handler(drv, acct, whs, mission_source),
                                    "Monitoring": monitoring_handler(drv, acct, whs),
                                    "LossPrevention": loss_prevention_handler(drv, acct, whs),
                                    "Insight": insight_handler(drv, acct, whs, wording=_wording(), cache_dir=_insight_cache())})
    if args.once:
        agent.poll_once()
        return 0
    print(f"agent runner for {args.run}/{args.company} polling every {args.interval:g}s; Ctrl+C to stop")
    try:
        agent.serve(args.interval)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

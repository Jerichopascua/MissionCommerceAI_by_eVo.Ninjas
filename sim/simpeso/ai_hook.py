"""Glue between the simulator and the MissionCommerce AI core (ai/missionai).

    python -m simpeso.ai_hook history --run demo1        # promo days so the model can learn price response
    python -m simpeso.ai_hook trial   --run demo1 --agent on|off
    python -m simpeso.ai_hook find    --run demo1        # risk-ranked stock counts, writes ai_findings.json
    python -m simpeso.ai_hook report  --run demo1

The AI side only ever sees what a tenant tool can read from PesoWeb (expiry risk, ledger movements, receipts, its own
actions) plus the tenant's own promo calendar. Shopper behavior and its hidden price response stay on the sim side."""
import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[2] / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from missionai import detectors                                   # noqa: E402
from missionai.agent import MarkdownAgent                         # noqa: E402
from missionai.demand import DemandModel                          # noqa: E402
from missionai.recorder import PredictionRecorder                 # noqa: E402

from . import incidents as inc, rng, runner                       # noqa: E402

HISTORY_DAYS = (100, 101, 102, 103, 104, 105)
BASELINE_DAYS = 2
PROMO_LADDER = (0.9, 0.8, 0.7, 0.6)
TRIAL_DAY = 200
LOT_FACTOR = 1.6          # trial lots hold this many days of normal demand: enough that some would go to waste


class OwnerClient:
    """The agent's view of PesoWeb for one company: its owner's own API access."""

    def __init__(self, driver, acct):
        self.driver, self.acct = driver, acct

    def policy(self) -> dict:
        return self.driver.pricing_policy(self.acct)

    def expiry_batches(self, warehouse_id: int) -> list:
        return self.driver.expiry_batches(self.acct, warehouse_id)

    def markdown(self, warehouse_id, product_id, batch_id, new_price, reason, ref):
        return self.driver.markdown(self.acct, warehouse_id, product_id, batch_id, new_price, reason, ref, "Ai")


class AiHooks:
    def __init__(self, ctx, agent_on: bool = True, endpoint: str = None):
        self.ctx, self.agent_on, self.endpoint = ctx, agent_on, endpoint
        self.model = DemandModel()
        self.recorder = PredictionRecorder(ctx.run_dir / "predictions.jsonl")
        self.rates = {}                 # (warehouse, product) -> units/day at list price
        self.ratios = {}                # (branch key, product code) -> price ratio shoppers see now
        self.agents = {}
        self.actions = []
        self.promo_day = False
        self.lots = False
        self.lot_batches = {}           # (warehouse, batch id) -> quantity at the start of the trial day
        self.cursor = {}                # warehouse -> last ledger movement id read
        self.hour_units = {}
        self.promo_today = {}
        self.day = 0
        self._catalog = {}
        for comp in ctx.plan.companies:
            cs = ctx.state["companies"][comp.key]
            for p in comp.catalog:
                self._catalog[cs["products"][p.code]] = {"company": comp.key, "code": p.code, "category": p.category,
                                                         "list_price": p.price, "cost": p.cost, "name": p.name, "expiry": p.expiry}

    # ---- helpers -------------------------------------------------------------------------------------------
    def live_branches(self):
        for comp in self.ctx.plan.companies:
            for bkey, bs in self.ctx.state["companies"][comp.key]["branches"].items():
                if "warehouse_id" in bs:
                    yield comp.key, bkey, bs["warehouse_id"]

    def batches(self, owner, wh) -> list:
        """All stocked expiry batches as rows shaped like the expiry feed (batchId, daysLeft, qtyOnHand, ...)."""
        today = dt.date.today()
        out = []
        for b in self.ctx.driver.all_batches(owner, wh):
            if not b.get("expiryDate"):
                continue
            days = (dt.date.fromisoformat(b["expiryDate"][:10]) - today).days
            out.append({"batchId": b["id"], "productId": b["productId"], "batchNo": b.get("batchNo") or "", "daysLeft": days,
                        "qtyOnHand": b["qtyOnHand"], "unitCost": b.get("cost") or 0})
        return out

    def product_info(self, pid):
        info = self._catalog.get(pid)
        return None if not info else {"category": info["category"], "list_price": info["list_price"], "discount_pct": 0, "name": info["name"]}

    def base_per_day(self, wh, pid):
        return self.rates.get((wh, pid))

    def _agent(self, ckey):
        if ckey not in self.agents:
            self.agents[ckey] = MarkdownAgent(OwnerClient(self.ctx.driver, self.ctx.owner(ckey)), self.model, self.recorder,
                                              self.product_info, self.base_per_day, endpoint=self.endpoint)
        return self.agents[ckey]

    # ---- hooks the runner calls ----------------------------------------------------------------------------
    def ratio(self, bkey, code) -> float:
        return self.ratios.get((bkey, code), 1.0)

    def start_day(self, ctx, day):
        self.day = day
        if self.lots:
            self._inject_lots()
        if self.promo_day:
            self._start_promos(day)

    def before_hour(self, ctx, hour):
        self._refresh_ratios()
        if self.agent_on:
            for ckey in ctx.cmap:
                whs = [wh for c, _, wh in self.live_branches() if c == ckey]
                if whs:
                    self.actions += [{**a, "day": self.day} for a in self._agent(ckey).tick(hour, whs)]

    def end_day(self, ctx, day, stats):
        if self.promo_day:
            self._end_promos()
        self._refresh_ratios()
        if self.actions:
            with (ctx.run_dir / "ai_actions.jsonl").open("a", encoding="utf-8") as f:
                for a in self.actions:
                    f.write(json.dumps(a, sort_keys=True) + "\n")
            self.actions = []

    # ---- prices shoppers see ---------------------------------------------------------------------------------
    def _refresh_ratios(self):
        drv = self.ctx.driver
        self.ratios = {}
        for ckey, bkey, wh in self.live_branches():
            owner = self.ctx.owner(ckey)
            active = {r["batchId"]: float(r["price"]) for r in drv.active_markdown_rows(owner, wh)}
            if not active:
                continue
            front = {}
            for b in self.batches(owner, wh):
                if float(b["qtyOnHand"]) > 0 and (b["productId"] not in front or b["daysLeft"] < front[b["productId"]]["daysLeft"]):
                    front[b["productId"]] = b
            for pid, b in front.items():
                if b["batchId"] in active and pid in self._catalog:
                    info = self._catalog[pid]
                    self.ratios[(bkey, info["code"])] = active[b["batchId"]] / info["list_price"]

    # ---- trial lots ------------------------------------------------------------------------------------------
    def _inject_lots(self):
        """Short-dated perishable lots sized to some multiple of normal demand, so a markdown has something to do."""
        ctx, drv = self.ctx, self.ctx.driver
        today = dt.date.today()
        self.lot_batches = {}
        for ckey, bkey, wh in self.live_branches():
            comp, cs = ctx.cmap[ckey], ctx.state["companies"][ckey]
            owner = ctx.owner(ckey)
            lines = []
            for p in comp.catalog:
                pid = cs["products"][p.code]
                rate = self.rates.get((wh, pid))
                if not p.expiry or not rate:
                    continue
                qty = max(4, math.ceil(rate * LOT_FACTOR))
                lines.append({"product_id": pid, "unit_cost": p.cost, "quantity": qty, "batch_no": f"lot-{self.day}-{bkey}-{p.code}",
                              "expiry_date": (today + dt.timedelta(days=1)).isoformat(), "manufacturing_date": (today - dt.timedelta(days=1)).isoformat()})
            if lines:
                drv.receive_stock(owner, wh, cs["suppliers"][0], lines, today.isoformat())
            for b in self.batches(owner, wh):
                if str(b.get("batchNo", "")).startswith(f"lot-{self.day}-"):
                    self.lot_batches[(wh, b["batchId"])] = {"qty": float(b["qtyOnHand"]), "cost": float(b["unitCost"]), "product_id": b["productId"]}

    # ---- history promos (the tenant's own promo calendar) ------------------------------------------------------
    def _start_promos(self, day):
        ctx, drv = self.ctx, self.ctx.driver
        self.promo_today = {}
        for ckey, bkey, wh in self.live_branches():
            owner = ctx.owner(ckey)
            r = rng.derive(ctx.state["seed"], "promo", day, bkey)
            batches = self.batches(owner, wh)
            by_product = {}
            for b in batches:
                if float(b["qtyOnHand"]) > 0:
                    by_product.setdefault(b["productId"], []).append(b)
            for pid in sorted(by_product):
                if pid not in self._catalog or r.random() < 0.5:
                    continue
                ratio = r.choice(PROMO_LADDER)
                price = round(self._catalog[pid]["list_price"] * ratio, 2)
                ok = False
                for b in by_product[pid]:
                    status, _ = drv.markdown(owner, wh, pid, b["batchId"], price, "promo calendar", None, "Manual")
                    ok = ok or status == 200
                if ok:
                    self.promo_today[(wh, pid)] = ratio

    def _end_promos(self):
        drv = self.ctx.driver
        for ckey, bkey, wh in self.live_branches():
            owner = self.ctx.owner(ckey)
            for row in drv.active_markdown_rows(owner, wh):
                drv.end_markdown(owner, row["id"], "promo day over")

    # ---- learning from the ledger ----------------------------------------------------------------------------
    def harvest(self, baseline: bool) -> dict:
        """Units sold per (warehouse, product) since the last harvest, plus the hour-of-day histogram."""
        units = {}
        for ckey, bkey, wh in self.live_branches():
            owner = self.ctx.owner(ckey)
            rows = self.ctx.driver.movements(owner, wh, "SALE_OUT", self.cursor.get(wh, 0))
            for m in rows:
                units[(wh, m["productId"])] = units.get((wh, m["productId"]), 0.0) + float(m["qtyOut"])
                if m.get("transactionDate"):
                    h = dt.datetime.fromisoformat(m["transactionDate"]).hour
                    self.hour_units[h] = self.hour_units.get(h, 0.0) + float(m["qtyOut"])
                self.cursor[wh] = max(self.cursor.get(wh, 0), m["id"])
        return units

    def run_history(self, log=print) -> dict:
        ctx = self.ctx
        self.agent_on = False
        base_units = {}
        for i, day in enumerate(HISTORY_DAYS):
            self.promo_day = i >= BASELINE_DAYS
            self.promo_today = {}
            self.harvest(True)                                  # move the cursor past earlier days
            runner.run_day(ctx, day, log=lambda *_: None, hooks=self, incidents=False)
            units = self.harvest(not self.promo_day)
            if not self.promo_day:
                for k, u in units.items():
                    base_units.setdefault(k, []).append(u)
                if i == BASELINE_DAYS - 1:
                    self.rates = {k: max(0.2, sum(v) / len(v)) for k, v in base_units.items()}
            else:
                for (wh, pid), ratio in self.promo_today.items():
                    info = self._catalog[pid]
                    if (wh, pid) in self.rates:
                        self.model.observe(info["category"], self.rates[(wh, pid)], ratio, units.get((wh, pid), 0.0))
            log(f"history day {day}: {'promo' if self.promo_day else 'baseline'}, {sum(units.values()):.0f} units")
        self.model.fit_hours(self.hour_units)
        self.promo_day = False
        cats = sorted({i["category"] for i in self._catalog.values() if i["expiry"]})
        learned = {c: round(self.model.beta(c), 2) for c in cats}
        self.save_model(learned)
        return learned

    def save_model(self, learned):
        (self.ctx.run_dir / "model.json").write_text(json.dumps({
            "betas": learned, "prior_beta": self.model.prior_beta,
            "rates": {f"{wh}:{pid}": r for (wh, pid), r in self.rates.items()},
            "hour_units": self.hour_units, "cursor": self.cursor,
            "observations": {c: list(map(list, v)) for c, v in self.model._obs.items()}}, indent=1), encoding="utf-8")

    def load_model(self):
        path = self.ctx.run_dir / "model.json"
        d = json.loads(path.read_text(encoding="utf-8"))
        self.rates = {tuple(map(int, k.split(":"))): v for k, v in d["rates"].items()}
        self.hour_units = {int(h): v for h, v in d["hour_units"].items()}
        self.cursor = {int(k): v for k, v in d["cursor"].items()}
        for c, obs in d["observations"].items():
            self.model._obs[c] = [tuple(o) for o in obs]
        self.model.fit_hours(self.hour_units)

    # ---- trial ------------------------------------------------------------------------------------------------
    def run_trial(self, day=TRIAL_DAY, log=print) -> dict:
        ctx, drv = self.ctx, self.ctx.driver
        self.lots, self.promo_day = True, False
        stats = runner.run_day(ctx, day, log=lambda *_: None, hooks=self, incidents=False)
        self.lots = False
        waste = revenue_lost = 0.0
        resolved = []
        for ckey, bkey, wh in self.live_branches():
            owner = ctx.owner(ckey)
            left = {b["batchId"]: float(b["qtyOnHand"]) for b in self.batches(owner, wh)}
            for (w, batch_id), lot in self.lot_batches.items():
                if w != wh:
                    continue
                qty_left = left.get(batch_id, 0.0)
                waste += qty_left * lot["cost"]
                for rec in list(self.recorder.items.values()):
                    if rec["batch_id"] == batch_id and rec["warehouse_id"] == wh and "realized" not in rec:
                        sold = rec["qty"] - qty_left
                        avg_price = rec["net_price"]
                        self.recorder.resolve(rec["id"], max(0.0, sold), avg_price)
                        resolved.append(rec["id"])
        stats["trial_waste_pesos"] = waste
        stats["lot_batches"] = len(self.lot_batches)
        stats["markdowns_applied"] = sum(1 for a in self._all_actions() if a.get("status") == "applied")
        stats["markdowns_refused"] = sum(1 for a in self._all_actions() if a.get("status") == "refused")
        stats["predictions_resolved"] = len(resolved)
        return stats

    def _all_actions(self):
        path = self.ctx.run_dir / "ai_actions.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---- incident finding by risk-ranked counts ---------------------------------------------------------------------
def find_incidents(ctx, k: int = 4, log=print) -> list:
    drv = ctx.driver
    findings = []
    for comp in ctx.plan.companies:
        cs = ctx.state["companies"][comp.key]
        owner = ctx.owner(comp.key)
        pid_code = {pid: code for code, pid in cs["products"].items()}
        costs = {p.code: p.cost for p in comp.catalog}
        receipts, sales, unit_costs, branch_of = [], {}, {}, {}
        for bkey, bs in cs["branches"].items():
            if "warehouse_id" not in bs:
                continue
            wh = bs["warehouse_id"]
            branch_of[wh] = (bkey, bs)
            receipts += drv.receipts(owner, wh)
            for m in drv.movements(owner, wh, "SALE_OUT"):
                sales[(wh, m["productId"])] = sales.get((wh, m["productId"]), 0.0) + float(m["qtyOut"])
            for pid, code in pid_code.items():
                unit_costs[(wh, pid)] = costs[code]
        targets = detectors.rank_count_targets(receipts, sales, unit_costs, k)
        by_wh = {}
        for t in targets:
            by_wh.setdefault(t.warehouse_id, []).append(t.product_id)
        results = []
        for wh, pids in by_wh.items():
            bkey, bs = branch_of[wh]
            count = drv.create_count(owner, wh, pids, "AI risk-ranked count")
            lines = count.get("lines") or []
            loss = bs.setdefault("physical_loss", {})
            counts = []
            for ln in lines:
                pid = ln["productId"]
                system = float(ln["systemQty"])
                code = pid_code[pid]
                counted = max(0.0, system - float(loss.get(code, 0)))          # the physical world, played by the sim
                counts.append({"productId": pid, "countedQty": counted, "reason": "count"})
                results.append({"warehouse_id": wh, "branch": bkey, "product_id": pid, "system_qty": system, "counted_qty": counted})
                loss[code] = 0                                                  # approving the count aligns the system with the shelf
            drv.submit_count(owner, count["count"]["id"], counts)
            drv.approve_count(owner, count["count"]["id"])
        findings += detectors.findings_from_counts(results, receipts)
        log(f"{comp.key}: counted {sum(len(v) for v in by_wh.values())} SKUs, {len([f for f in findings if f['branch'].startswith(comp.key)])} finding(s)")
    ctx.save()
    path = ctx.run_dir / "ai_findings.json"
    known = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    merged = {f["id"]: f for f in known}
    merged.update({f["id"]: f for f in findings})          # findings accumulate across passes
    path.write_text(json.dumps(list(merged.values()), indent=2), encoding="utf-8")
    return list(merged.values())


# ---- CLI --------------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.ai_hook")
    ap.add_argument("command", choices=["history", "trial", "find", "report"])
    ap.add_argument("--run", default="run1")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--agent", choices=["on", "off"], default="on")
    ap.add_argument("--k", type=int, default=4, help="stock-count budget per branch")
    ap.add_argument("--endpoint", default=os.environ.get("VLLM_URL"))
    args = ap.parse_args(argv)
    ns = argparse.Namespace(run=args.run, base_url=args.base_url, seed=21, profile="smoke", policy="off")
    ctx = runner._load(ns)
    hooks = AiHooks(ctx, agent_on=args.agent == "on", endpoint=args.endpoint)
    if args.command == "history":
        print(json.dumps({"learned_log_price_slopes": hooks.run_history()}, indent=2))
    elif args.command == "trial":
        hooks.load_model()
        print(json.dumps(hooks.run_trial(), indent=2))
        print(json.dumps(hooks.recorder.calibration(), indent=2))
    elif args.command == "find":
        print(json.dumps(find_incidents(ctx, args.k), indent=2))
    else:
        print(json.dumps(hooks.recorder.calibration(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

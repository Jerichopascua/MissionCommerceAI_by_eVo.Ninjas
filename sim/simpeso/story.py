"""The customer story: a neighbourhood buys cooked whole chickens that must go tonight. Customers think for themselves
(see customers.py); the shop is the real PesoWeb with a markdown agent allowed to cut prices from 20:30.

    python -m simpeso.story --arm learning --days 14 --seed 3          # one arm, prints Marco's diary and what the system saw
    python -m simpeso.story --compare --days 14 --seeds 1-3 --out ../results/story.json

Arms (same seeded neighbourhood, same shop, same chickens):
    none      no clearance at all
    naive     the agent clears at 20:30, customers never change their habits (the old statistical shopper)
    learning  the agent clears at 20:30, customers notice, ask, wait, tell friends and adapt

PesoWeb runs on the real clock, so the evening clock (17:00 to 22:00) is the simulator's. Stock, shelf prices, markdowns
and every price paid come from PesoWeb. The system's behavior-change detector sees only purchase records."""
import argparse
import datetime as dt
import json
import os
import statistics
import sys
import uuid
from pathlib import Path

from . import customers as cu, rng
from .ai_hook import AI_DIR     # noqa: F401  (puts ai/ on sys.path)
from .driver import PesoWebDriver
from .verticals import ProductSpec

from missionai import behavior_shift                                # noqa: E402
from missionai.agent import MarkdownAgent                           # noqa: E402
from missionai.demand import DemandModel                            # noqa: E402
from missionai.recorder import PredictionRecorder                   # noqa: E402

LIST_PRICE, COST, LOT = 250, 110, 12
BASELINE_DAYS = 3
CLEARANCE_FROM = 20.5
HOUR_PRIOR = 0.3          # list-price sales under-show late demand (people who would buy cheaper); see demand.fit_hours
ARMS = ("none", "naive", "learning")


def ticks():
    t = cu.OPEN
    while t < cu.CLOSE:
        yield t
        t += cu.STEP


# ---- one evening, independent of PesoWeb ---------------------------------------------------------------------
def run_night(people, shop, day: int, seed: int) -> dict:
    """shop interface: tick(hour), price(), stock(), buy(qty) -> total paid, cashier_hint() -> hour or None."""
    for c in people:
        c.start_night(day, rng.derive(seed, "night", day, c.id), LIST_PRICE)
    events, waited, tips, cut_hour, bought_by = [], 0, 0, None, {}
    for t in ticks():
        shop.tick(t)
        price = shop.price()
        if cut_hour is None and price < 0.95 * LIST_PRICE:
            cut_hour = t
        for c in people:
            if c.state == "idle" and c.wants and c.arrival is not None and c.arrival <= t:
                c.state = "here"
                c.note(t, f"arrived at the shop, chicken is {price:.0f}")
                if cut_hour is not None and c.last_price is None and price < 0.95 * LIST_PRICE:
                    c.saw_cut(t, exact=False)
        for c in people:
            if c.state != "here":
                continue
            if c.last_price is not None and c.last_price >= 0.95 * LIST_PRICE and price < 0.95 * LIST_PRICE:
                c.saw_cut(t, exact=True)
            c.last_price = price
            rnd = rng.derive(seed, "decide", day, c.id, int(t * 4))
            action, qty = c.decide(cu.Observation(t, price, LIST_PRICE, shop.stock()), rnd)
            if action == "buy":
                paid = shop.buy(qty)
                events.append({"day": day, "hour": t, "price": paid / qty, "list_price": LIST_PRICE, "qty": qty, "who": c.id})
                c.note(t, f"bought {qty} at {paid / qty:.0f} each" + (" (a bargain, so I took extra)" if qty > 1 else ""))
                c.history.append((day, c.arrival, qty, paid / qty))
                c.state = "done"
                bought_by[c.id] = qty
                if price <= 0.6 * LIST_PRICE and rnd.random() < c.traits.sociability:
                    for f in c.friends:
                        f.told(cut_hour if cut_hour is not None else t, "a friend", at=t)
                        tips += 1
                    c.note(t, f"told {len(c.friends)} friends about it")
            elif action == "ask":
                c.asked = True
                c.told(shop.cashier_hint(), "cashier", at=t)
            elif action == "wait":
                if c.state == "here" and not getattr(c, "_waiting_noted", None) == day:
                    c._waiting_noted = day
                    waited += 1
                    c.note(t, f"chicken is {price:.0f}, too much; I will wait")
            else:
                c.note(t, "left without buying" + (" (sold out)" if shop.stock() <= 0 else f" (price {price:.0f} was above what I can pay)"))
                if shop.stock() <= 0 and cut_hour is not None:
                    c.missed_out(t)
                c.state = "done"
    for c in people:
        if c.state == "here":
            c.note(cu.CLOSE, "shop closed before I could buy")
            c.state = "done"
    return {"events": events, "waited": waited, "tips": tips, "cut_hour": cut_hour}


# ---- the real shop -------------------------------------------------------------------------------------------
class PesoShop:
    """One shop on the real PesoWeb. Every day: a fresh product with a lot of chickens expiring tomorrow."""

    def __init__(self, base_url: str, run: str, arm: str):
        self.drv = PesoWebDriver(base_url, run)
        self.arm = arm
        self.acct = self.drv.register(f"Chicken Corner {run}", "Shop", "Owner", f"{run}@story.test", "Story!12345")
        self.wh = self.acct.warehouse_id
        self.basics = self.drv.setup_basics(self.acct)
        self.cat = self.drv.add_category(self.acct, "Cooked food")
        self.sup = self.drv.add_supplier(self.acct, "Chicken Supplier", 1)
        self.cust = int(self.drv.customers(self.acct)[0]["id"])
        mode = "Off" if arm == "none" else "Autonomous"
        self.drv.set_pricing_policy(self.acct, mode, hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=6)
        self.model = DemandModel(prior_beta=-1.5)
        self.recorder = PredictionRecorder(Path(os.environ.get("TEMP", ".")) / f"story_{run}.jsonl")
        self.rate_samples, self.hour_units = [], {}
        self.cut_hours, self.pid, self.batch_id, self.day = [], None, None, 0
        self.agent_on = False
        self.agent = MarkdownAgent(_Client(self), self.model, self.recorder, self._info, self._rate, not_before_hour=CLEARANCE_FROM)

    def _info(self, pid):
        if pid != self.pid:
            return None                      # only tonight's chickens: older unsold lots have no buyers and are not worth acting on
        return {"category": "Cooked food", "list_price": LIST_PRICE, "discount_pct": 0, "name": f"Cooked Whole Chicken D{self.day}"}

    def _rate(self, wh, pid):
        return statistics.mean(self.rate_samples) if len(self.rate_samples) >= BASELINE_DAYS else None

    def open_day(self, day: int) -> None:
        self.day = day
        spec = ProductSpec(f"CHK-{day}", f"Cooked Whole Chicken D{day}", "Cooked food", COST, LIST_PRICE, True, (1, 1), 1)
        self.pid = self.drv.add_product(self.acct, spec, self.cat, self.basics)
        today = dt.date.today()
        self.drv.receive_stock(self.acct, self.wh, self.sup, [{"product_id": self.pid, "unit_cost": COST, "quantity": LOT,
                               "batch_no": f"LOT-D{day}", "expiry_date": (today + dt.timedelta(days=1)).isoformat(),
                               "manufacturing_date": today.isoformat()}], today.isoformat())
        self.batch_id = next(b["id"] for b in self.drv.all_batches(self.acct, self.wh) if b["productId"] == self.pid)
        self._price, self._left, self._cut_today = float(LIST_PRICE), LOT, None
        self.agent.applied.clear()
        self.agent.predictions.clear()
        self.agent_on = self.arm != "none" and day >= BASELINE_DAYS

    # shop interface for run_night
    def tick(self, hour):
        if self.agent_on and hour >= CLEARANCE_FROM:
            acts = self.agent.tick(hour, [self.wh])
            if any(a.get("status") == "applied" for a in acts) and self._cut_today is None:
                self._cut_today = hour
        rows = [r for r in self.drv.active_markdown_rows(self.acct, self.wh) if r["batchId"] == self.batch_id]
        self._price = float(rows[0]["price"]) if rows else float(LIST_PRICE)

    def price(self):
        return self._price

    def stock(self):
        return self._left

    def buy(self, qty):
        sale = self.drv.sell(self.acct, self.wh, self.cust, [(self.pid, qty)], "Cash", self._price * qty)
        self._left -= qty
        return float(sale["totalAmount"])

    def cashier_hint(self):
        return statistics.median(self.cut_hours) if self.cut_hours else None

    def close_day(self, events) -> dict:
        left = next((float(b["qtyOnHand"]) for b in self.drv.all_batches(self.acct, self.wh) if b["id"] == self.batch_id), 0.0)
        sold = LOT - left
        if self._cut_today is not None:
            self.cut_hours.append(self._cut_today)
        if self.day < BASELINE_DAYS:
            self.rate_samples.append(sold)
            for e in events:
                h = int(e["hour"])
                self.hour_units[h] = self.hour_units.get(h, 0.0) + e["qty"]
            if self.day == BASELINE_DAYS - 1:
                self.model.fit_hours(self.hour_units, prior_share=HOUR_PRIOR)
        for rec in list(self.recorder.items.values()):
            if "realized" not in rec and rec["batch_id"] == self.batch_id:
                self.recorder.resolve(rec["id"], sold, rec["net_price"])
        revenue = sum(e["price"] * e["qty"] for e in events)
        full = sum(e["qty"] for e in events if e["price"] >= 0.95 * LIST_PRICE)
        return {"day": self.day, "sold": sold, "left": left, "waste_pesos": left * COST, "revenue": revenue,
                "margin": revenue - sold * COST, "net": revenue - sold * COST - left * COST,
                "full_price_units": full, "discount_units": sold - full, "cut_hour": self._cut_today}


class _Client:
    def __init__(self, shop):
        self.shop = shop

    def policy(self):
        return self.shop.drv.pricing_policy(self.shop.acct)

    def expiry_batches(self, wh):
        return self.shop.drv.expiry_batches(self.shop.acct, wh)

    def markdown(self, wh, pid, batch, price, reason, ref):
        return self.shop.drv.markdown(self.shop.acct, wh, pid, batch, price, reason, ref, "Ai")


# ---- arms ----------------------------------------------------------------------------------------------------
def run_arm(base_url: str, arm: str, days: int, seed: int, log=print, heroes=None, llm=None) -> dict:
    people = cu.build_population(seed, adaptive=(arm == "learning"))
    hero_list = []
    if heroes:                                   # a few shoppers whose judgement comes from an AI API (simpeso/llm_hero.py)
        from . import llm_hero
        hero_list = llm_hero.add_heroes(people, heroes, llm)
    shop = PesoShop(base_url, f"story-s{seed}-{arm}-{uuid.uuid4().hex[:4]}", arm)
    per_day, events, nights = [], [], []
    for day in range(days):
        shop.open_day(day)
        night = run_night(people, shop, day, seed)
        stats = shop.close_day(night["events"])
        stats.update(waited=night["waited"], tips=night["tips"])
        per_day.append(stats)
        events += [{k: e[k] for k in ("day", "hour", "price", "list_price", "qty")} for e in night["events"]]
        log(f"  {arm:8s} day {day:2d}: sold {stats['sold']:.0f}/{LOT} (full {stats['full_price_units']:.0f}, clearance {stats['discount_units']:.0f}) "
            f"waste {stats['waste_pesos']:.0f}  cut at {cu.clock(stats['cut_hour']) if stats['cut_hour'] else '-':>5s}  waited {night['waited']}  tips {night['tips']}")
    after = list(range(max(BASELINE_DAYS, days - 5), days))
    result = {"arm": arm, "seed": seed, "days": per_day,
              "shift": behavior_shift.detect_shift(events, range(BASELINE_DAYS), after, seed=seed) if arm != "none" else None,
              "calibration": shop.recorder.calibration(), "marco": [(d, cu.clock(h), t) for d, h, t in people[0].diary]}
    if hero_list:
        result["heroes"] = {"summary": llm_hero.summary(hero_list, llm),
                            "diaries": {h.name: {"persona": h.hero.persona, "mission": h.hero.mission,
                                                 "diary": [(d, cu.clock(hh), tx) for d, hh, tx in h.diary]} for h in hero_list}}
    late = per_day[BASELINE_DAYS:]
    for k in ("waste_pesos", "revenue", "margin", "net", "full_price_units", "discount_units"):
        result[k] = statistics.mean(d[k] for d in late)
    return result


def compare(base_url: str, days: int, seeds: list, log=print) -> dict:
    runs = {s: {arm: run_arm(base_url, arm, days, s, log) for arm in ARMS} for s in seeds}
    keys = ("waste_pesos", "revenue", "margin", "net", "full_price_units", "discount_units")
    summary = {arm: {k: statistics.mean(runs[s][arm][k] for s in seeds) for k in keys} for arm in ARMS}
    return {"days": days, "seeds": seeds, "baseline_days": BASELINE_DAYS, "summary": summary, "runs": runs,
            "note": "Per-evening means over the days after the baseline. The customers' judgement is a rule-based utility model, "
                    "an assumption of this simulator, not measured human behavior."}


def parse_seeds(text):
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.story")
    ap.add_argument("--arm", choices=ARMS, default="learning")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--seeds", default="1-3")
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--heroes", type=int, default=0, help="this many shoppers get their judgement from an AI API instead of the rules")
    ap.add_argument("--personas", default=None, help="a JSONL file of synthetic personas (for example a Nemotron-Personas sample); default: four built in")
    ap.add_argument("--llm", choices=["env", "stub"], default="env",
                    help="env: the AI API named by ANTHROPIC_API_KEY or LLM_BASE_URL/LLM_MODEL (see simpeso/llm_hero.py); stub: an offline stand-in, no key, no network")
    ap.add_argument("--max-llm-calls", type=int, default=300, help="the most real AI API calls a run may make (cached answers are free)")
    args = ap.parse_args(argv)
    heroes = llm = None
    if args.heroes:
        from . import llm_hero
        specs = llm_hero.load_personas(args.personas, args.heroes, args.seed) if args.personas else llm_hero.BUILT_IN[:args.heroes]
        if args.llm == "stub":
            llm = llm_hero.LlmClient("openai", "stub", "http://stub", transport=llm_hero.stub_transport, max_calls=10 ** 9)
        else:
            llm = llm_hero.LlmClient.from_env(cache_path=llm_hero.RUNS / "llm_cache.jsonl", max_calls=args.max_llm_calls)
        heroes = specs
        print(f"hero shoppers: {len(specs)} using {llm}")
    if args.compare:
        res = compare(args.base_url, args.days, parse_seeds(args.seeds))
        text = json.dumps(res, indent=1, default=float)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        print(json.dumps(res["summary"], indent=1, default=float))
        return 0
    res = run_arm(args.base_url, args.arm, args.days, args.seed, heroes=heroes, llm=llm)
    print("\nMarco's diary:")
    for d, h, t in res["marco"]:
        print(f"  day {d:2d} {h}  {t}")
    for name, h in (res.get("heroes", {}).get("diaries") or {}).items():
        print(f"\n{name}: {h['persona']}\n  mission: {h['mission']}")
        for d, hh, tx in h["diary"][-8:]:
            print(f"  day {d:2d} {hh}  {tx}")
    if res.get("heroes"):
        print("\nHero shoppers:", res["heroes"]["summary"])
    if res["shift"]:
        print("\nWhat the system saw:", res["shift"]["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

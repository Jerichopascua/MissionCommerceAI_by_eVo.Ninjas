"""Runner: build the corporate world through the real API, run seeded business days, score the incidents.

    python -m simpeso.runner build --base-url http://localhost:5071 --seed 21 --profile smoke --run r1
    python -m simpeso.runner day   --run r1 --day 0
    python -m simpeso.runner score --run r1

Root (central company) credentials come from PESOWEB_ROOT_EMAIL / PESOWEB_ROOT_PASSWORD; they are used only to raise
a subsidiary's plan tier and are never written to disk. Day indexes pick the dice; PesoWeb itself runs on the real clock."""
import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

from . import behavior, incidents as inc, rng, scoring, world
from .driver import Account, DriverError, DriverRefusal, PesoWebDriver

RUNS = Path(__file__).resolve().parent.parent / "runs"
OPENING_CASH = 1000
SHIFT_OPEN_HOUR, SHIFT_CLOSE_HOUR = 5, 24
RETURN_RATE = 0.02


class Context:
    def __init__(self, driver: PesoWebDriver, plan, state: dict, run_dir: Path, root: Account = None, calib=None):
        self.driver, self.plan, self.state, self.run_dir, self.root = driver, plan, state, run_dir, root
        self.calib = calib                  # optional real-data calibration of shopper behavior (calibration.py)
        self._tokens = {}
        self.cmap = {c.key: c for c in plan.companies}
        self.bmap = {b.key: (c, b) for c in plan.companies for b in c.branches}

    def save(self) -> None:
        (self.run_dir / "world.json").write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def account(self, email: str, password: str) -> Account:
        key = (email, password)
        if key not in self._tokens:
            self._tokens[key] = self.driver.login(email, password)
        return self._tokens[key]

    def owner(self, ckey: str) -> Account:
        o = self.state["companies"][ckey]["owner"]
        return self.account(o["email"], o["password"])

    def cashier(self, bkey: str) -> Account:
        c, b = self.bmap[bkey]
        s = self.state["companies"][c.key]["branches"][bkey]["staff"][b.staff[0].key]
        return self.account(s["email"], s["password"])


MAX_LINES_PER_PURCHASE = 60      # PesoWeb rejects forms with more than 1,024 values; each line is about 8 values


def chunks(items: list, n: int = MAX_LINES_PER_PURCHASE):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _tagged(email: str, tag: str) -> str:
    return email.replace("@", f".{tag}@")


def _today() -> dt.date:
    return dt.date.today()


def _batches(spec, qty: int, r) -> list:
    """Two staggered batches for an expiry product (so FEFO has a real choice); one plain line otherwise."""
    if not spec.expiry:
        return [{"qty": qty, "expiry": None, "made": None}]
    lo, hi = spec.shelf_life_days
    first = max(2, round(lo + (hi - lo) * r.uniform(0.2, 0.5)))
    second = max(first + 1, round(lo + (hi - lo) * r.uniform(0.7, 1.0)))
    q1 = max(1, round(qty * 0.55))
    return [{"qty": q1, "days": first, "shelf": hi}, {"qty": max(1, qty - q1), "days": second, "shelf": hi}]


def _lines_for(ctx: Context, ckey: str, bkey: str, demand: dict, seed: int) -> list:
    comp = ctx.cmap[ckey]
    products = ctx.state["companies"][ckey]["products"]
    lines = []
    for spec in comp.catalog:
        qty = max(30, math.ceil(demand.get((bkey, spec.code), 0) * 25))
        r = rng.derive(seed, "batch", bkey, spec.code)
        for n, b in enumerate(_batches(spec, qty, r)):
            line = {"product_id": products[spec.code], "unit_cost": spec.cost, "quantity": b["qty"]}
            if spec.expiry:
                line.update(batch_no=f"{bkey}-{spec.code}-{n + 1}",
                            expiry_date=(_today() + dt.timedelta(days=b["days"])).isoformat(),
                            manufacturing_date=(_today() - dt.timedelta(days=1)).isoformat())
            lines.append(line)
    return lines


def estimate_demand(plan, seed: int, people=None, calib=None) -> dict:
    people = people or behavior.make_individuals(plan, seed)
    out = {}
    for d in (1, 2, 3):
        for v in behavior.day_visits(plan, people, d, seed, calib=calib):
            for code, q in v.lines:
                out[(v.branch, code)] = out.get((v.branch, code), 0) + q / 3
    return out


# ---- build -------------------------------------------------------------------------------------------------
def build_branch(ctx: Context, ckey: str, bkey: str, demand: dict, first: bool = False) -> None:
    drv, comp = ctx.driver, ctx.cmap[ckey]
    cstate = ctx.state["companies"][ckey]
    bstate = cstate["branches"].setdefault(bkey, {"staff": {}})
    owner = ctx.owner(ckey)
    _, bplan = ctx.bmap[bkey]
    if "warehouse_id" not in bstate:
        bstate["warehouse_id"] = owner.warehouse_id if first else drv.add_branch(owner, bplan.name, bplan.city, len(cstate["branches"]))
        ctx.save()
    if not first and not bstate.get("granted"):
        drv.grant_branch(owner, bstate["warehouse_id"])
        bstate["granted"] = True
    for s in bplan.staff:
        if s.key not in bstate["staff"]:
            drv.add_staff(owner, cstate["role_id"], s.name, s.username + ctx.state["tag"], _tagged(s.email, ctx.state["tag"]), s.password, bstate["warehouse_id"])
            bstate["staff"][s.key] = {"email": _tagged(s.email, ctx.state["tag"]), "password": s.password}
    if not bstate.get("stocked"):
        lines = _lines_for(ctx, ckey, bkey, demand, ctx.state["seed"])
        for part in chunks(lines):
            drv.receive_stock(owner, bstate["warehouse_id"], cstate["suppliers"][0], part, _today().isoformat())
        bstate["stocked"] = True
    ctx.save()


def build(ctx: Context, log=print) -> None:
    drv, plan = ctx.driver, ctx.plan
    demand = estimate_demand(plan, ctx.state["seed"], calib=ctx.calib)
    for comp in plan.companies:
        cs = ctx.state["companies"].setdefault(comp.key, {"branches": {}})
        if cs.get("done"):
            continue
        o = comp.owner
        email = _tagged(o.email, ctx.state["tag"])
        first, last = (o.name.split(" ", 1) + [""])[:2]
        acct = drv.register(comp.name, first, last or "Owner", email, o.password)
        cs["owner"] = {"email": email, "password": o.password, "tenant_id": acct.tenant_id, "user_id": acct.user_id}
        ctx.save()
        if ctx.root:
            drv.root_set_tier(ctx.root, acct, comp.tier)
        ctx._tokens.pop((email, o.password), None)
        owner = ctx.owner(comp.key)
        cs["basics"] = drv.setup_basics(owner)
        cs["categories"] = {c: drv.add_category(owner, c) for c in sorted({p.category for p in comp.catalog})}
        cs["suppliers"] = [drv.add_supplier(owner, s.name, i + 1) for i, s in enumerate(comp.suppliers)]
        cs["role_id"] = drv.role_id(owner)
        cs["customer_id"] = int(drv.customers(owner)[0]["id"])
        pol = ctx.state.get("policy")
        if pol:
            drv.set_pricing_policy(owner, pol["mode"], pol["hard"], pol["soft"], pol["max_discount"], pol["max_changes"])
        cs["products"] = {p.code: drv.add_product(owner, p, cs["categories"][p.category], cs["basics"]) for p in comp.catalog}
        ctx.save()
        for n, b in enumerate(comp.branches):
            if b.opens_hour:
                continue                       # expansion branches are built mid-run
            try:
                build_branch(ctx, comp.key, b.key, demand, first=(n == 0))
            except DriverRefusal as exc:
                cs.setdefault("refusals", []).append({"branch": b.key, "message": exc.message})
                log(f"  {comp.key}: {b.key} refused by PesoWeb ({exc.message})")
        cs["done"] = True
        ctx.save()
        log(f"built {comp.key} {comp.name}: tenant {acct.tenant_id}, {sum(1 for b in cs['branches'].values() if 'warehouse_id' in b)} branches, {len(cs['products'])} products")


# ---- day ---------------------------------------------------------------------------------------------------
def _find_batch_id(drv, acct, wh: int, batch_no: str):
    for b in drv.near_expiry(acct, wh):
        if b.get("batchNo") == batch_no:
            return b.get("id")
    return None


def run_day(ctx: Context, day: int, log=print, hooks=None, incidents: bool = True) -> dict:
    drv, plan, seed = ctx.driver, ctx.plan, ctx.state["seed"]
    people = behavior.make_individuals(plan, seed)
    arrivals = behavior.day_arrivals(plan, people, day, seed, calib=ctx.calib)
    planned = inc.plan_incidents(plan, seed, day) if incidents else []
    ledger = inc.Ledger.load(ctx.run_dir / "ledger.json") if (ctx.run_dir / "ledger.json").exists() else inc.Ledger()
    action_log, stats = [], {"sales": 0, "sale_failed": 0, "returns": 0, "refusals": 0, "units": 0, "revenue": 0.0, "cogs": 0.0}
    shifts = {}

    def live(bkey):
        c, _ = ctx.bmap[bkey]
        return "warehouse_id" in ctx.state["companies"][c.key]["branches"].get(bkey, {})

    # shifts open before trading starts
    for ckey in ctx.cmap:
        for bkey, b in ((b.key, b) for b in ctx.cmap[ckey].branches):
            if b.opens_hour == 0 and live(bkey):
                wh = ctx.state["companies"][ckey]["branches"][bkey]["warehouse_id"]
                shifts[bkey] = drv.open_shift(ctx.cashier(bkey), wh, "POS-01", OPENING_CASH)
                action_log.append({"t": "open_shift", "branch": bkey})

    timeline = [(v.hour, v.minute, 1, v) for v in arrivals]
    timeline += [(e["hour"], 0, 0, e) for e in plan.expansions if e["day"] == day]
    timeline += [(i.hour, 30, 0, i) for i in planned if i.type not in (inc.CASH_SHORT, inc.NEAR_EXPIRY_BATCH)]
    timeline.sort(key=lambda t: (t[0], t[1], t[2], getattr(t[3], "id", "") if not isinstance(t[3], dict) else t[3]["branch"]))
    cash_short = {i.branch: i for i in planned if i.type == inc.CASH_SHORT}
    ratio_fn = getattr(hooks, "ratio", None)
    cur_hour = SHIFT_OPEN_HOUR + 1
    if hooks:
        hooks.start_day(ctx, day)
        hooks.before_hour(ctx, cur_hour)
    demand = None
    sale_n = 0
    for hour, minute, _, item in timeline:
        while hooks and cur_hour < hour:
            cur_hour += 1
            hooks.before_hour(ctx, cur_hour)
        if isinstance(item, dict):                                  # a branch opens mid-run
            if demand is None:
                demand = estimate_demand(plan, seed, people, calib=ctx.calib)
            ckey, bkey = item["company"], item["branch"]
            try:
                build_branch(ctx, ckey, bkey, demand)
                wh = ctx.state["companies"][ckey]["branches"][bkey]["warehouse_id"]
                shifts[bkey] = drv.open_shift(ctx.cashier(bkey), wh, "POS-01", OPENING_CASH)
                log(f"  hour {hour}: {ckey} opened {bkey} (warehouse {wh})")
            except DriverRefusal as exc:
                stats["refusals"] += 1
                ctx.state["companies"][ckey].setdefault("refusals", []).append({"branch": bkey, "message": exc.message})
                log(f"  hour {hour}: {bkey} opening refused ({exc.message})")
            action_log.append({"t": "expansion", "branch": bkey, "hour": hour})
            continue
        if isinstance(item, inc.Incident):
            _inject(ctx, item, ledger, action_log)
            continue
        v = behavior.fill_basket(plan, item, seed, ratio_fn, ctx.calib)
        if v is None or v.branch not in shifts or not live(v.branch):
            continue
        c, _b = ctx.bmap[v.branch]
        cs = ctx.state["companies"][c.key]
        wh = cs["branches"][v.branch]["warehouse_id"]
        spec_price = {p.code: p.price for p in c.catalog}
        spec_cost = {p.code: p.cost for p in c.catalog}
        lines = [(cs["products"][code], q) for code, q in v.lines]
        total = sum(round(spec_price[code] * (ratio_fn(v.branch, code) if ratio_fn else 1.0), 2) * q for code, q in v.lines)
        action_log.append({"t": "sale", "visit": v.id, "branch": v.branch, "lines": list(v.lines)})
        try:
            sale = drv.sell(ctx.cashier(v.branch), wh, cs["customer_id"], lines, v.payment, total)
            stats["sales"] += 1
            stats["units"] += sum(q for _, q in v.lines)
            stats["cogs"] += sum(spec_cost[code] * q for code, q in v.lines)
            stats["revenue"] += float(sale.get("totalAmount") or 0)
            sale_n += 1
            if sale.get("id") and rng.derive(seed, "return", v.id).random() < RETURN_RATE:
                code, q = v.lines[0]
                drv.return_sale(ctx.cashier(v.branch), sale["id"], wh, cs["customer_id"], [(cs["products"][code], 1)], _today().isoformat())
                stats["returns"] += 1
                action_log.append({"t": "return", "visit": v.id})
        except DriverError as exc:
            stats["sale_failed"] += 1
            stats.setdefault("failure_samples", [])
            if len(stats["failure_samples"]) < 3:
                stats["failure_samples"].append(str(exc)[:160])

    if hooks:
        while cur_hour < SHIFT_CLOSE_HOUR - 1:
            cur_hour += 1
            hooks.before_hour(ctx, cur_hour)
        hooks.end_day(ctx, day, stats)

    # a short-dated delivery lands after trading stops: FEFO would otherwise sell it through before any alert could fire
    for i in planned:
        if i.type == inc.NEAR_EXPIRY_BATCH:
            _inject(ctx, i, ledger, action_log)

    # close every shift: the drawer matches PesoWeb's expected cash, except natural noise and injected shortages
    for bkey, shift_id in shifts.items():
        c, b = ctx.bmap[bkey]
        wh = ctx.state["companies"][c.key]["branches"][bkey]["warehouse_id"]
        cashier = ctx.cashier(bkey)
        expected = float(drv.current_shift(cashier, wh)["summary"]["expectedCash"])
        r = rng.derive(seed, "cashnoise", day, bkey)
        noise = r.choice([-5, -2, -1, 1, 2, 5]) if r.random() < (1 - b.staff[0].accuracy) * 1.5 else 0
        shortage = cash_short[bkey].detail["amount"] if bkey in cash_short else 0
        drv.close_shift(cashier, shift_id, expected + noise - shortage, "end of day count")
        action_log.append({"t": "close_shift", "branch": bkey, "noise": noise, "shortage": shortage})
        if bkey in cash_short:
            i = cash_short[bkey]
            i.warehouse_id = wh
            ledger.add(i)
            action_log.append({"t": "incident", "id": i.id})

    # PesoWeb's detection pass (the nightly job); the sim triggers it through the real endpoint
    for ckey in ctx.cmap:
        cs = ctx.state["companies"][ckey]
        for bkey, bs in cs["branches"].items():
            if "warehouse_id" in bs:
                drv.detect_exceptions(ctx.owner(ckey), bs["warehouse_id"])
    ledger.save(ctx.run_dir / "ledger.json")
    ctx.save()
    stats["action_log_hash"] = rng.stable_hash(action_log)
    stats["actions"] = len(action_log)
    stats["incidents_injected"] = len(ledger.incidents)
    return stats


def _inject(ctx: Context, incident: inc.Incident, ledger: inc.Ledger, action_log: list) -> None:
    drv = ctx.driver
    c, b = ctx.bmap[incident.branch]
    cs = ctx.state["companies"][c.key]
    bs = cs["branches"][incident.branch]
    wh = bs["warehouse_id"]
    incident.warehouse_id = wh
    owner = ctx.owner(c.key)
    spec = next((p for p in c.catalog if p.code == incident.detail.get("product_code")), None)
    if incident.type == inc.NEAR_EXPIRY_BATCH:
        batch_no = f"{incident.id}-short-dated"
        line = {"product_id": cs["products"][spec.code], "unit_cost": spec.cost, "quantity": incident.detail["units"],
                "batch_no": batch_no, "expiry_date": (_today() + dt.timedelta(days=incident.detail["days_left"])).isoformat(),
                "manufacturing_date": (_today() - dt.timedelta(days=5)).isoformat()}
        drv.receive_stock(owner, wh, cs["suppliers"][0], [line], _today().isoformat())
        incident.detail["batch_no"] = batch_no
        incident.detail["batch_id"] = _find_batch_id(drv, owner, wh, batch_no)
    elif incident.type == inc.UNREPORTED_SHORT_DELIVERY:
        n = incident.detail["units_recorded"]
        line = {"product_id": cs["products"][spec.code], "unit_cost": spec.cost, "quantity": n}
        if spec.expiry:
            line.update(batch_no=f"{incident.id}-delivery", expiry_date=(_today() + dt.timedelta(days=max(10, spec.shelf_life_days[0]))).isoformat(),
                        manufacturing_date=(_today() - dt.timedelta(days=1)).isoformat())
        drv.receive_stock(owner, wh, cs["suppliers"][0], [line], _today().isoformat())     # no receiving report on purpose
        loss = bs.setdefault("physical_loss", {})
        loss[spec.code] = loss.get(spec.code, 0) + (n - incident.detail["units_arrived"])
    elif incident.type == inc.HIDDEN_SHRINK:
        # physical loss only: PesoWeb is never told. Kept so a later stock count can reveal it.
        loss = bs.setdefault("physical_loss", {})
        loss[incident.detail["product_code"]] = loss.get(incident.detail["product_code"], 0) + incident.detail["units"]
    ledger.add(incident)
    action_log.append({"t": "incident", "id": incident.id})


# ---- score -------------------------------------------------------------------------------------------------
def score_run(ctx: Context) -> scoring.Scorecard:
    ledger = inc.Ledger.load(ctx.run_dir / "ledger.json")
    rows = []
    for ckey in ctx.cmap:
        rows += ctx.driver.exceptions(ctx.owner(ckey))
    findings_path = ctx.run_dir / "ai_findings.json"
    findings = json.loads(findings_path.read_text(encoding="utf-8")) if findings_path.exists() else []
    card = scoring.score(ledger.incidents, rows, findings)
    (ctx.run_dir / "scorecard.json").write_text(json.dumps(card.summary(), indent=2), encoding="utf-8")
    return card


# ---- CLI ---------------------------------------------------------------------------------------------------
def _load(args) -> Context:
    run_dir = RUNS / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "world.json"
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    else:
        state = {"run": args.run, "seed": args.seed, "profile": args.profile, "tag": args.run, "companies": {}}
        if args.policy != "off":
            state["policy"] = {"mode": {"autonomous": "Autonomous", "approval": "Approval"}[args.policy], "hard": args.hard_floor, "soft": args.soft_floor,
                               "max_discount": args.max_discount, "max_changes": 6}
    cat = state.get("catalog") or ({"path": args.catalog, "size": args.catalog_size, "perishables": bool(getattr(args, "perishables", False))}
                                   if getattr(args, "catalog", None) else None)
    if cat and not state.get("catalog"):
        state["catalog"] = cat
    items = json.loads(Path(cat["path"]).read_text(encoding="utf-8"))["items"] if cat else None
    plan = world.plan_group(state["seed"], state["profile"], catalog=items, catalog_size=cat["size"] if cat else None,
                            perishables=bool(cat and cat.get("perishables")))
    drv = PesoWebDriver(args.base_url, args.run)
    root = None
    if os.environ.get("PESOWEB_ROOT_PASSWORD"):
        root = drv.login(os.environ.get("PESOWEB_ROOT_EMAIL", "superadmin@email.com"), os.environ["PESOWEB_ROOT_PASSWORD"])
    calib = None
    if getattr(args, "calibration", None):
        from . import calibration
        calib = calibration.load(args.calibration, weight=args.calib_weight)
        pop = behavior.make_individuals(plan, state["seed"])
        scale = calibration.fit_basket_scale(plan, pop, state["seed"], json.loads(Path(args.calibration).read_text(encoding="utf-8"))["all"]["lines_per_sale_mean"])
        calib = calibration.Calibration(calib.hour_share, calib.weight, scale, calib.outside_hours_share)
    return Context(drv, plan, state, run_dir, root, calib)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.runner")
    ap.add_argument("command", choices=["build", "day", "score", "all"])
    ap.add_argument("--base-url", default=os.environ.get("PESOWEB_URL", "http://localhost:5071"))
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--profile", default="smoke", choices=sorted(world.PROFILES))
    ap.add_argument("--run", default="run1")
    ap.add_argument("--day", type=int, default=0)
    ap.add_argument("--hard-floor", type=float, default=10, help="hard margin floor, percent over cost")
    ap.add_argument("--soft-floor", type=float, default=20, help="soft margin floor, percent over cost")
    ap.add_argument("--max-discount", type=float, default=50)
    ap.add_argument("--catalog", default=None, help="path to a real catalog json (sim/runs/real_catalog.json): every company and branch sells it")
    ap.add_argument("--catalog-size", type=int, default=None, help="use only the N best sellers plus a seeded sample (default: all)")
    ap.add_argument("--perishables", action="store_true", help="with --catalog real: mark products matching the explicit perishable name rules (simpeso/perishables.py) as expiry-tracked")
    ap.add_argument("--calibration", default=None, help="path to real-calibration.json: use the real hour profile and basket size")
    ap.add_argument("--calib-weight", type=float, default=0.5, help="weight on the real hour profile (the sample is small)")
    ap.add_argument("--policy", choices=["off", "autonomous", "approval"], default="off", help="pricing autonomy set at build")
    args = ap.parse_args(argv)
    ctx = _load(args)
    if args.command in ("build", "all"):
        build(ctx)
    if args.command in ("day", "all"):
        print(json.dumps(run_day(ctx, args.day), indent=2))
    if args.command in ("score", "all"):
        print(json.dumps(score_run(ctx).summary(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

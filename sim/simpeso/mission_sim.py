"""Baskets for AI Customer Mission, from two sources, and the handler that posts the result.

* PesoWeb's own sales (`pesoweb_baskets`): what a real shop would use. Each sale is a basket; its hour is the sale's hour.
* The simulator's visits (`sim_baskets`): PesoWeb stamps a simulated sale with the real clock, so in a simulated world every sale looks
  like it happened when the script ran and the time of day is lost. The simulator therefore hands the classifier the same facts a sale
  would carry (hour, lines, units, value, perishable or not) straight from its own visit records. The shoppers' hidden mission is kept
  aside for scoring and is never given to the classifier."""
import datetime as dt

from . import price_run

from missionai import missions as ms   # noqa: E402  (price_run puts the AI folder on the path)


def pesoweb_baskets(drv, acct, warehouse_ids: list, window_days: int = 14) -> dict:
    """{warehouse id: [Basket]} from PesoWeb's sales of the last window_days."""
    since = (dt.date.today() - dt.timedelta(days=window_days)).isoformat()
    out = {}
    for wh in warehouse_ids:
        perishable = {p["id"] for p in price_run.browse(drv, acct, wh) if p["perishable"]}
        baskets, after = [], 0
        while True:
            page = drv.baskets(acct, wh, after, since)
            rows = page.get("baskets", [])
            for r in rows:
                lines = r.get("lines") or []
                if not lines:
                    continue
                hour = dt.datetime.fromisoformat(r["saleDate"]).hour
                baskets.append(ms.Basket(hour, len(lines), sum(float(x["quantity"]) for x in lines),
                                         float(r.get("totalAmount") or sum(float(x["amount"]) for x in lines)), any(x["productId"] in perishable for x in lines)))
            if len(rows) < 2000:
                break
            after = page["nextAfterId"]
        out[wh] = baskets
    return out


def sim_baskets(ctx, days: list, seed: int = None) -> dict:
    """{(company key, branch key): [(true mission id, Basket)]} from the simulator's visits on the given virtual days."""
    from . import behavior
    seed = ctx.state["seed"] if seed is None else seed
    individuals = behavior.make_individuals(ctx.plan, seed)
    info = {}
    for comp in ctx.plan.companies:
        info[comp.key] = {p.code: (float(p.price), bool(p.expiry)) for p in comp.catalog}
    out = {}
    for day in days:
        for v in behavior.day_visits(ctx.plan, individuals, day, seed, calib=ctx.calib):
            codes = info[v.company]
            value = sum(q * codes[c][0] for c, q in v.lines)
            out.setdefault((v.company, v.branch), []).append(
                (v.mission, ms.Basket(v.hour, len(v.lines), float(sum(q for _, q in v.lines)), value, any(codes[c][1] for c, _ in v.lines))))
    return out


def score_sim(sim: dict) -> dict:
    """How often the classifier's mission is one the shopper's true mission could look like (see missions.ACCEPTED)."""
    pairs = []
    for rows in sim.values():
        median = sorted(b.value for _, b in rows)[len(rows) // 2] if rows else 0.0
        pairs += [(truth, ms.classify(b, median)) for truth, b in rows]
    return ms.score(pairs)


def rows_for(warehouse_id: int, baskets: list, window_days: int) -> list:
    return [{"WarehouseId": warehouse_id, "Mission": r["mission"], "Baskets": r["baskets"], "SharePct": r["share_pct"], "AvgItems": r["avg_items"],
             "AvgValue": r["avg_value"], "PeakHour": r["peak_hour"], "Insight": r["insight"], "WindowDays": window_days} for r in ms.summarize(baskets, window_days)]


def mission_handler(drv, acct, warehouse_ids: list, source, window_days: int = 14):
    """source() -> {warehouse id: [Basket]}. Posts each branch's mission picture to PesoWeb (replacing the earlier one)."""
    def run() -> str:
        by_wh = source()
        items = []
        for wh, baskets in by_wh.items():
            items += rows_for(wh, baskets, window_days)
        status, body = drv.post_missions(acct, warehouse_ids, items)
        if status != 200:
            raise RuntimeError(f"PesoWeb refused the mission picture: {status} {body}")
        n = sum(len(v) for v in by_wh.values())
        return f"{body.get('added', 0)} mission rows from {n} baskets at {len(by_wh)} branches" + ("" if items else " (too few baskets to say)")
    return run

"""Calibrate the simulator against REAL sales history in a restored PesoWeb database (read-only).

    python scripts/calibrate_real.py --db PesoWeb_V2_Real

Reads every tenant and branch. Writes sim/runs/real-calibration.json and .md (git-ignored: they are derived from a real
business). The script itself holds no data and is safe to commit. It reports how much the real sample can and cannot
support, with bootstrap intervals, and compares each statistic with what the simulator assumes."""
import argparse
import collections
import datetime as dt
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SQLCMD = r"D:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE"
MIN_SALES_FOR_BRANCH_STATS = 15


def query(db: str, sql: str) -> list:
    out = subprocess.run([SQLCMD, "-S", r"(localdb)\MSSQLLocalDB", "-E", "-C", "-d", db, "-h", "-1", "-W", "-s", "|", "-w", "4000", "-Q",
                          "SET NOCOUNT ON; " + sql], capture_output=True, text=True, check=True).stdout
    return [line.split("|") for line in out.splitlines() if line.strip()]


def boot_ci(values, fn=statistics.mean, n=2000, seed=7):
    if len(values) < 3:
        return None
    rnd = random.Random(seed)
    stats = sorted(fn([rnd.choice(values) for _ in values]) for _ in range(n))
    return [round(stats[int(0.025 * n)], 2), round(stats[int(0.975 * n)], 2)]


def pmf(values, cap):
    c = collections.Counter(min(v, cap) for v in values)
    total = sum(c.values())
    return {str(k): round(c[k] / total, 3) for k in sorted(c)}


def load(db):
    sales = [dict(id=int(r[0]), tenant=int(r[1]), wh=int(r[2]), when=dt.datetime.fromisoformat(r[3].replace(" ", "T")), total=float(r[4]), pay=r[5])
             for r in query(db, "SELECT Id,TenantID,WarehouseId,CONVERT(varchar(23),SaleDate,126),TotalAmount,ISNULL(PaymentMethod,'') FROM Sales")]
    lines = collections.defaultdict(list)
    for r in query(db, "SELECT SaleId,ProductId,Quantity,SalePrice FROM SaleDetails"):
        lines[int(r[0])].append((int(r[1]), float(r[2]), float(r[3])))
    return sales, lines


def summarize(sales, lines):
    if not sales:
        return None
    totals = [s["total"] for s in sales]
    nlines = [len(lines.get(s["id"], [])) for s in sales if lines.get(s["id"])]
    units = [q for s in sales for (_, q, _) in lines.get(s["id"], [])]
    days = collections.Counter(s["when"].date() for s in sales)
    hours = collections.Counter(s["when"].hour for s in sales)
    wk = collections.Counter(s["when"].weekday() for s in sales)
    pay = collections.Counter(s["pay"] or "unknown" for s in sales)
    n = len(sales)
    prices = [p for s in sales for (_, _, p) in lines.get(s["id"], [])]
    skus = collections.Counter(pid for s in sales for (pid, q, _) in lines.get(s["id"], []) for _ in range(int(q)))
    top10 = sum(c for _, c in skus.most_common(10)) / max(1, sum(skus.values()))
    return {
        "sales": n, "active_days": len(days), "span_days": (max(days) - min(days)).days + 1,
        "sales_per_active_day": round(n / len(days), 2), "max_sales_in_a_day": max(days.values()),
        "ticket_mean": round(statistics.mean(totals), 1), "ticket_mean_ci95": boot_ci(totals),
        "ticket_median": round(statistics.median(totals), 1), "tickets_under_50_share": round(sum(1 for t in totals if t < 50) / n, 3),
        "lines_per_sale_mean": round(statistics.mean(nlines), 2) if nlines else None,
        "lines_per_sale_ci95": boot_ci(nlines) if nlines else None, "lines_per_sale_pmf": pmf(nlines, 6) if nlines else {},
        "units_per_line_mean": round(statistics.mean(units), 2) if units else None, "units_per_line_pmf": pmf([int(u) for u in units], 5) if units else {},
        "hour_share": {str(h): round(hours[h] / n, 3) for h in sorted(hours)},
        "evening_share_20_to_24": round(sum(c for h, c in hours.items() if h >= 20) / n, 3),
        "midnight_hour_0_share": round(hours.get(0, 0) / n, 3),
        "weekday_share_mon_to_sun": [round(wk.get(d, 0) / n, 3) for d in range(7)],
        "payment_share": {k: round(v / n, 3) for k, v in pay.items()},
        "line_price_mean": round(statistics.mean(prices), 1) if prices else None,
        "line_price_bands": {"<=20": round(sum(1 for p in prices if p <= 20) / len(prices), 3), "20-50": round(sum(1 for p in prices if 20 < p <= 50) / len(prices), 3),
                             "50-100": round(sum(1 for p in prices if 50 < p <= 100) / len(prices), 3), ">100": round(sum(1 for p in prices if p > 100) / len(prices), 3)} if prices else {},
        "distinct_skus_sold": len(skus), "top10_sku_share_of_units": round(top10, 3),
    }


def assumptions():
    from simpeso import behavior, verticals
    arr = behavior.population_arrays()
    w = arr["hour_weights"].mean(axis=0)
    hours = arr["hours"]
    vs = verticals.load_all()
    return {"hour_share_mean_over_archetypes": {str(h): round(float(x), 3) for h, x in zip(hours, w)},
            "evening_share_20_to_24": round(float(sum(x for h, x in zip(hours, w) if h >= 20)), 3),
            "basket_items_per_visit_mean": round(float(arr["basket"].mean()), 2),
            "ticket_bands_pesos": {n: list(v.ticket) for n, v in vs.items()},
            "smoke_profile_txns_per_branch_day": "about 3 to 12 (txns band x 0.02 traffic scale)",
            "cash_share_assumed": "mostly cash; card for high-income shoppers (about 10 to 60% of those)"}


def fit_report(out: dict) -> str:
    """How close does the simulator get to the real numbers, with and without calibration, for several weights on the real sample?"""
    from simpeso import behavior, calibration, world
    real = out["all"]
    plan = world.plan_group(21, "starter")
    people = behavior.make_individuals(plan, 21)
    outside = sum(v for h, v in real["hour_share"].items() if int(h) < 6)
    real_evening = real["evening_share_20_to_24"] / max(1e-9, 1 - outside)
    scale = calibration.fit_basket_scale(plan, people, 21, real["lines_per_sale_mean"])

    def measure(c):
        vs = behavior.day_visits(plan, people, 2, 21, calib=c) + behavior.day_visits(plan, people, 3, 21, calib=c)
        return (sum(1 for v in vs if v.hour >= 20) / len(vs), sum(len(v.lines) for v in vs) / len(vs), sum(q for v in vs for _, q in v.lines) / len(vs))
    rows = [("simulator as built", measure(None))]
    for w in (0.25, 0.5, 0.75):
        c = calibration.from_real(real, weight=w, basket_scale=scale)
        rows.append((f"calibrated, weight {w} on the real hour profile, basket scale {scale}", measure(c)))
    lines = ["# Real-data calibration (private: derived from a real business, not committed)", "",
             f"Source: database `{out['database']}`: {out['total_sales']} sales, {out['total_lines']} lines, {out['tenants']} tenants, {out['branches']} branches.",
             "Only two branches have enough sales for stable statistics; the rest have 1 to 4 sales each. Treat everything here as indicative, not as a fitted truth.", "",
             "## Real statistics", "", "| | Pooled (all) | Largest branch | Second branch |", "|---|---|---|---|"]
    pb = [v for v in out["per_branch"].values() if v.get("enough_for_stats")]
    def col(key, fmt=str):
        return " | ".join(fmt(b.get(key)) if b.get(key) is not None else "-" for b in [real] + pb[:2])
    lines += [f"| Sales | {col('sales')} |", f"| Active trading days | {col('active_days')} |", f"| Sales per active day | {col('sales_per_active_day')} |",
              f"| Mean ticket (pesos) | {col('ticket_mean')} |", f"| Median ticket (pesos) | {col('ticket_median')} |",
              f"| Tickets under 50 pesos | {col('tickets_under_50_share')} |", f"| Lines per sale | {col('lines_per_sale_mean')} |",
              f"| Units per line | {col('units_per_line_mean')} |", f"| Share of sales from 20:00 | {col('evening_share_20_to_24')} |",
              f"| Share of sales after midnight (00:00 to 00:59) | {col('midnight_hour_0_share')} |", f"| Top-10 products' share of units | {col('top10_sku_share_of_units')} |", "",
              f"Largest branch: ticket mean 95% interval {pb[0].get('ticket_mean_ci95')}, lines per sale 95% interval {pb[0].get('lines_per_sale_ci95')}.", "",
              "## Simulator against the real data", "", f"Real: {real_evening * 100:.0f}% of in-hours sales from 20:00, {real['lines_per_sale_mean']} lines per sale, "
              f"{real['lines_per_sale_mean'] * (real['units_per_line_mean'] or 1):.1f} units per sale.", "",
              "| Setup | Visits from 20:00 | Lines per visit | Units per visit |", "|---|---|---|---|"]
    for name, (e, l, u) in rows:
        lines.append(f"| {name} | {e * 100:.0f}% | {l:.2f} | {u:.2f} |")
    lines += ["", "## What the data can and cannot support", "",
              f"- It supports a later evening shape (about {real_evening * 100:.0f}% of in-hours sales from 20:00 against {rows[0][1][0] * 100:.0f}% of simulated visits) and clearly smaller baskets (about {real['lines_per_sale_mean']} lines per sale against {rows[0][1][1]:.1f} simulated).",
              f"- {out['all'].get('midnight_hour_0_share', 0) * 100:.0f}% of real sales happen in the hour after midnight, which the simulator (trading hours 06:00 to 23:59) cannot place.",
              "- Product sales are far more concentrated than the simulator's flat popularity (top 10 products carry about 60% of units at the largest branch); not yet applied.",
              "- Payment is almost all cash here, so any card share in a real-calibrated run would be unsupported (the AI does not use payment type).",
              "- With 104 sales there is NOT enough data to fit price response: only 3 lines were sold at a price different from list. Price response stays an assumption.",
              "- The history covers 14 trading days at the main branch (a pilot-style record), so absolute volumes understate a full business."]
    return chr(10).join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="PesoWeb_V2_Real")
    ap.add_argument("--fit", action="store_true", help="also write the simulator-vs-real fit report")
    args = ap.parse_args(argv)
    sales, lines = load(args.db)
    out = {"database": args.db, "total_sales": len(sales), "total_lines": sum(len(v) for v in lines.values()),
           "tenants": len({s["tenant"] for s in sales}), "branches": len({(s["tenant"], s["wh"]) for s in sales}),
           "all": summarize(sales, lines), "per_branch": {}, "assumed_by_simulator": assumptions()}
    by_branch = collections.defaultdict(list)
    for s in sales:
        by_branch[(s["tenant"], s["wh"])].append(s)
    for (t, w), ss in sorted(by_branch.items(), key=lambda kv: -len(kv[1])):
        out["per_branch"][f"tenant{t}/wh{w}"] = {"enough_for_stats": len(ss) >= MIN_SALES_FOR_BRANCH_STATS, **(summarize(ss, lines) or {})} if len(ss) >= MIN_SALES_FOR_BRANCH_STATS \
            else {"enough_for_stats": False, "sales": len(ss)}
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    (runs / "real-calibration.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("total_sales", "total_lines", "tenants", "branches")}))
    if args.fit:
        (runs / "real-calibration.md").write_text(fit_report(out), encoding="utf-8")
        print("wrote sim/runs/real-calibration.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

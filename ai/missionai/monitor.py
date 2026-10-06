"""AI Monitoring: finding what is out of the ordinary for a branch by comparing it with its own recent past.

PesoWeb's rules already catch fixed limits (expired stock, any cash difference, selling below cost). This module adds what a fixed
limit cannot: a branch whose sales fell by half, a single cash difference far larger than that branch's usual one, a cashier who is
short again and again, a burst of returns and deleted sales, and stock that no longer adds up to the ledger. Every finding says what
was seen, against what, and is worded as "differs from usual", never as an accusation. Plain statistics (median and spread of the
branch's own history), no model, so the reason is always one sentence long.

Each detector takes plain rows and returns findings: dicts with key (stable, so the same finding on the next scan updates the same
alert), warehouse_id, kind (Sales, Cash, Returns, Ledger), message and value."""
import datetime as dt
from statistics import median

MIN_HISTORY_DAYS = 7          # days of history needed before a sales comparison means anything
SALES_DROP = 0.5              # flag a day at or below this share of the branch's usual
SALES_SPIKE = 2.0             # flag a day at or above this multiple of usual (and several spreads away)
CASH_MIN_VARIANCE = 100.0     # a single cash difference smaller than this (pesos) is never flagged on its own
CASH_BIG_MULTIPLE = 3.0       # ... and must be this many times the branch's usual difference
CASH_REPEAT_MIN = 3           # a cashier short this many times in the recent shifts is flagged
CASH_REPEAT_WINDOW = 10
CASH_REPEAT_MIN_AMOUNT = 20.0
RETURNS_SHARE = 0.10          # returns and deleted sales above this share of the day's sales
RETURNS_MIN_EVENTS = 3
LEDGER_TOLERANCE = 0.0


def _peso(v: float) -> str:
    return f"₱{v:,.0f}"


def _mad(values: list, centre: float) -> float:
    return median(abs(v - centre) for v in values) if values else 0.0


def daily_totals(baskets: list) -> dict:
    """baskets: dicts with saleDate (ISO text) and totalAmount -> {date: total}."""
    out = {}
    for b in baskets:
        day = dt.datetime.fromisoformat(str(b["saleDate"])[:19]).date()
        out[day] = out.get(day, 0.0) + float(b.get("totalAmount") or 0)
    return out


def sales_findings(daily_by_branch: dict, names: dict, today: dt.date) -> list:
    """daily_by_branch: {warehouse id: {date: total}}. Looks at the latest completed day (before today), against the days before it."""
    out = []
    for wh, days in daily_by_branch.items():
        past = sorted(d for d in days if d < today)
        if len(past) < MIN_HISTORY_DAYS + 1:
            continue
        latest, history = past[-1], [days[d] for d in past[:-1]][-28:]
        usual = median(history)
        if usual <= 0:
            continue
        spread = max(1.4826 * _mad(history, usual), 0.10 * usual)
        value = days[latest]
        z = (value - usual) / spread
        name = names.get(wh, f"Branch {wh}")
        if value <= SALES_DROP * usual and z <= -3.0:
            out.append({"key": f"sales-drop:{wh}:{latest}", "warehouse_id": wh, "kind": "Sales", "value": round(100 * (1 - value / usual), 1),
                        "message": f"Sales at {name} on {latest:%b %d} were {_peso(value)}, {100 * (1 - value / usual):.0f}% below its usual {_peso(usual)} (the middle of its previous {len(history)} days)."})
        elif value >= SALES_SPIKE * usual and z >= 3.0:
            out.append({"key": f"sales-spike:{wh}:{latest}", "warehouse_id": wh, "kind": "Sales", "value": round(100 * (value / usual - 1), 1),
                        "message": f"Sales at {name} on {latest:%b %d} were {_peso(value)}, {100 * (value / usual - 1):.0f}% above its usual {_peso(usual)}. Worth knowing why (a promotion, a bulk order, a mistake)."})
    return out


def cash_findings(shifts: list, names: dict, cashiers: dict = None) -> list:
    """shifts: /api/ai/cash-shifts rows (closed). Flags one difference far above the branch's usual, and a cashier who is short again and again."""
    out, cashiers = [], cashiers or {}
    by_wh = {}
    for s in shifts:
        if s.get("variance") is not None and s.get("closedAt"):
            by_wh.setdefault(s["warehouseId"], []).append(s)
    for wh, rows in by_wh.items():
        rows.sort(key=lambda s: s["closedAt"])
        name = names.get(wh, f"Branch {wh}")
        usual = median(abs(float(s["variance"])) for s in rows)
        newest = rows[-1]
        for s in rows[-3:]:                                   # only the latest shifts are news; older ones were already seen
            v = float(s["variance"])
            if abs(v) >= CASH_MIN_VARIANCE and abs(v) >= CASH_BIG_MULTIPLE * max(usual, 1.0) and len(rows) >= 5:
                out.append({"key": f"cash-big:{s['id']}", "warehouse_id": wh, "kind": "Cash", "value": round(abs(v), 2),
                            "message": f"A cash shift at {name} closed {_peso(abs(v))} {'short' if v < 0 else 'over'}, far more than its usual difference of {_peso(usual)}."})
        by_cashier = {}
        for s in rows[-60:]:
            by_cashier.setdefault(s.get("cashierId"), []).append(s)
        for cid, mine in by_cashier.items():
            recent = mine[-CASH_REPEAT_WINDOW:]
            short = [s for s in recent if float(s["variance"]) <= -CASH_REPEAT_MIN_AMOUNT]
            if len(short) >= CASH_REPEAT_MIN and short[-1]["id"] >= rows[-5]["id"]:
                who = cashiers.get(cid, f"cashier {cid}")
                total = -sum(float(s["variance"]) for s in short)
                out.append({"key": f"cash-repeat:{wh}:{cid}", "warehouse_id": wh, "kind": "Cash", "value": round(total, 2),
                            "message": f"At {name}, shifts closed by {who} were short on {len(short)} of the last {len(recent)} ({_peso(total)} in all). It may be a counting habit or a till problem; worth a look together."})
    return out


def returns_findings(events: list, names: dict, today: dt.date) -> list:
    """events: /api/ai/events rows (eventType, warehouseId, occurredAt). Returns and deleted sales as a share of sales, today against the days before."""
    per = {}
    for e in events:
        t = e.get("eventType")
        if t not in ("SaleCompleted", "SaleReturned", "SaleDeleted") or e.get("warehouseId") is None:
            continue
        day = dt.datetime.fromisoformat(str(e["occurredAt"])[:19]).date()
        row = per.setdefault((e["warehouseId"], day), {"sales": 0, "bad": 0})
        row["sales" if t == "SaleCompleted" else "bad"] += 1
    out = []
    for wh in {k[0] for k in per}:
        days = {d: v for (w, d), v in per.items() if w == wh}
        past = [v for d, v in days.items() if d < today]
        past_sales, past_bad = sum(v["sales"] for v in past), sum(v["bad"] for v in past)
        usual = past_bad / past_sales if past_sales else 0.0
        for d, v in days.items():
            if d < today - dt.timedelta(days=1):
                continue
            share = v["bad"] / max(v["sales"], 1)
            if v["bad"] >= RETURNS_MIN_EVENTS and share >= RETURNS_SHARE and share >= 2 * usual:
                name = names.get(wh, f"Branch {wh}")
                out.append({"key": f"returns:{wh}:{d}", "warehouse_id": wh, "kind": "Returns", "value": round(100 * share, 1),
                            "message": f"At {name} on {d:%b %d}, {v['bad']} sales were returned or deleted against {v['sales']} completed ({100 * share:.0f}%), more than twice its usual {100 * usual:.1f}%."})
    return out


def ledger_findings(drift: list, names: dict, tolerance: float = LEDGER_TOLERANCE) -> list:
    """drift: /api/ai/ledger-drift rows. Stock on the shelf that no longer equals what the ledger says should be there."""
    by_wh = {}
    for r in drift:
        if abs(float(r["drift"])) > tolerance:
            by_wh.setdefault(r["warehouseId"], []).append(r)
    out = []
    for wh, rows in by_wh.items():
        worst = max(rows, key=lambda r: abs(float(r["drift"])))
        name = names.get(wh, f"Branch {wh}")
        out.append({"key": f"ledger:{wh}", "warehouse_id": wh, "kind": "Ledger", "value": float(len(rows)),
                    "message": f"At {name}, {len(rows)} product(s) have a shelf quantity that differs from the stock ledger (largest: product {worst['productId']}, {float(worst['drift']):+g}). A stock count would settle it."})
    return out


def all_findings(names: dict, today: dt.date, daily_sales: dict = None, shifts: list = None, events: list = None, drift: list = None,
                 cashiers: dict = None) -> list:
    out = []
    out += sales_findings(daily_sales or {}, names, today)
    out += cash_findings(shifts or [], names, cashiers)
    out += returns_findings(events or [], names, today)
    out += ledger_findings(drift or [], names)
    return out

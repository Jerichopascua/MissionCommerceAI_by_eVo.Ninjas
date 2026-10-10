"""Checking our models against real shoppers' data, for the data sets a person chooses.

    python -m simpeso.validate demand   --datasets dunnhumby            [--out FILE]
    python -m simpeso.validate demand   --datasets store-pos,m5
    python -m simpeso.validate missions --datasets till-survey

demand: for every product (and store) with real price variation, fit the price-aware demand model (the same DemandModel the shop's AI uses) on
the first part of the history and predict the last part, then compare the error (WAPE: total absolute error over total units) with plain
baselines that ignore price: the average, the recent average, and the same weekday last week. It reports the days where the price moved
away from usual separately, because that is where price awareness has to earn its place. If the price-aware model does not win, the report says so.

missions: the shopper's own answer to "why did you come today?" (collected at the till, with consent) against what AI Customer Mission infers
from the basket alone.

Neither test changes anything in PesoWeb. Data sets are the user's files (see simpeso/datasets.py); results are written to sim/runs/ (git-ignored)."""
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import datasets
from .ai_hook import AI_DIR     # noqa: F401  (puts ai/ on sys.path)

from missionai.demand import DemandModel        # noqa: E402
from missionai import missions as ms           # noqa: E402

RUNS = Path(__file__).resolve().parent.parent / "runs"
MIN_DAYS = 40
MIN_PRICE_SPREAD = 1.05       # the dearest day at least 5% above the cheapest, or there is nothing to learn about price
MIN_IMPROVEMENT = 0.02        # "better" means at least 2% lower error than the best baseline, so noise is not called a win
MOVED = 0.05                  # a day "with a price move" is one whose price is 5% or more away from the usual


@dataclass
class Series:
    key: str
    category: str
    days: list        # increasing day numbers (consecutive days; a day with no sale has 0 units)
    price: list
    units: list


# ---- loaders: real files into daily series ----------------------------------------------------------------------------
def _fill(days_units: dict, days_value: dict, key: str, category: str, min_days: int = MIN_DAYS):
    if not days_units:
        return None
    lo, hi = min(days_units), max(days_units)
    if hi - lo + 1 < min_days:
        return None
    days, price, units, last = [], [], [], None
    for d in range(lo, hi + 1):
        u = days_units.get(d, 0.0)
        if u > 0:
            last = days_value[d] / u
        if last is None:
            continue
        days.append(d)
        price.append(last)
        units.append(u)
    return Series(key, category, days, price, units) if len(days) >= min_days else None


MAX_LINE_QTY = 20          # a till line with more units than this is a weighed or bulk line, not a shelf item
MIN_SALES_DAYS = 200       # a product must have sold on at least this many days to be tested


def series_from_dunnhumby(base=None, top: int = 150, row_limit: int = 5_000_000) -> list:
    base = Path(base) if base else datasets.folder("dunnhumby")
    units, value = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    with (base / "transaction_data.csv").open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        up = {h.strip().upper(): h for h in (rd.fieldnames or [])}
        for n, r in enumerate(rd):
            if n >= row_limit:
                break
            try:
                q, v, d = float(r[up["QUANTITY"]]), float(r[up["SALES_VALUE"]]), int(r[up["DAY"]])
            except (KeyError, ValueError):
                continue
            if q <= 0 or q > MAX_LINE_QTY or v <= 0:
                continue
            p = r[up["PRODUCT_ID"]]
            units[p][d] += q
            value[p][d] += v
    eligible = [p for p in units if len(units[p]) >= MIN_SALES_DAYS]
    best = sorted(eligible, key=lambda p: -sum(units[p].values()))[:top]
    out = [s for s in (_fill(units[p], value[p], p, "all") for p in best) if s]
    return out


def series_from_store_pos(path=None, top: int = 150) -> list:
    base = datasets.folder("store-pos")
    path = Path(path) if path else next((base / n for n in ("receipts.csv", "sales.csv", "pos.csv") if (base / n).is_file()), None)
    if path is None:
        raise datasets.SelectionError("store-pos: no receipts file")
    import datetime as dt
    units, value, cats = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float)), {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        norm = {h.strip().lower().replace(" ", "_"): h for h in (rd.fieldnames or [])}

        def col(*names):
            return next((norm[n] for n in names if n in norm), None)
        item, when, qty, price = col("sku", "product_id", "product", "item", "item_code"), col("datetime", "date_time", "timestamp", "sale_date", "date"), \
            col("qty", "quantity", "units"), col("price", "unit_price", "selling_price")
        cat = col("category", "department")
        if not (item and when and price):
            raise datasets.SelectionError("store-pos: the demand check needs product, date and price columns (found: " + ", ".join(rd.fieldnames or []) + ")")
        for r in rd:
            try:
                day = dt.date.fromisoformat(r[when][:10]).toordinal()
                q = float(r[qty] or 1) if qty else 1.0
                p = float(r[price])
            except (ValueError, TypeError):
                continue
            if q <= 0 or p <= 0:
                continue
            units[r[item]][day] += q
            value[r[item]][day] += q * p
            cats[r[item]] = (r.get(cat) if cat else None) or "all"
    best = sorted(units, key=lambda p: -sum(units[p].values()))[:top]
    return [s for s in (_fill(units[p], value[p], p, cats.get(p, "all")) for p in best) if s]


def series_from_m5(base=None, top: int = 150) -> list:
    base = Path(base) if base else datasets.folder("m5")
    sales_name = next((n for n in ("sales_train_validation.csv", "sales_train_evaluation.csv") if (base / n).is_file()), None)
    if not sales_name:
        raise datasets.SelectionError("m5: no sales_train_*.csv")
    week_of = {}
    with (base / "calendar.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            week_of[r["d"]] = r["wm_yr_wk"]
    rows = []
    with (base / sales_name).open(newline="", encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        head = next(rd)
        dcols = [i for i, h in enumerate(head) if h.startswith("d_")]
        for r in rd:
            total = sum(float(r[i] or 0) for i in dcols)
            rows.append((total, r[head.index("item_id")], r[head.index("store_id")], r[head.index("cat_id")], [float(r[i] or 0) for i in dcols]))
    rows.sort(key=lambda x: -x[0])
    rows = rows[:top]
    want = {(i, s) for _, i, s, _, _ in rows}
    price = {}
    with (base / "sell_prices.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r["item_id"], r["store_id"]) in want:
                price[(r["item_id"], r["store_id"], r["wm_yr_wk"])] = float(r["sell_price"])
    dnames = [h for h in head if h.startswith("d_")]
    out = []
    for _, item, store, cat, daily in rows:
        days, pr, un = [], [], []
        for k, name in enumerate(dnames):
            p = price.get((item, store, week_of.get(name)))
            if p is None:
                continue                                      # the item was not on sale yet
            days.append(k)
            pr.append(p)
            un.append(daily[k])
        if len(days) >= MIN_DAYS:
            out.append(Series(f"{item}@{store}", cat, days, pr, un))
    return out


SERIES_LOADERS = {"dunnhumby": series_from_dunnhumby, "store-pos": series_from_store_pos, "m5": series_from_m5}


# ---- the back-test ------------------------------------------------------------------------------------------------------
def _wape(actual: list, predicted: list) -> float:
    total = sum(actual)
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / total if total > 0 else float("nan")


def backtest_price_model(series: list, train_share: float = 0.7, min_days: int = MIN_DAYS) -> dict:
    """Fit on the first part of every usable series, predict the rest, compare with price-blind baselines."""
    usable = []
    for s in series:
        n = len(s.days)
        if n < min_days:
            continue
        cut = int(n * train_share)
        tp = s.price[:cut]
        if min(tp) <= 0 or max(tp) / min(tp) < MIN_PRICE_SPREAD or sum(s.units[:cut]) <= 0:
            continue
        usable.append((s, cut))
    if not usable:
        return {"series_used": 0, "note": "no product has enough days and enough price variation in this data set to test price awareness"}

    model = DemandModel()
    fitted = []
    for s, cut in usable:
        ref = statistics.median(s.price[:cut])
        base = statistics.mean(s.units[:cut])
        fitted.append((s, cut, ref, base))
        for p, u in zip(s.price[:cut], s.units[:cut]):
            model.observe(s.category, base, p / ref, u)

    actual, aware, aware_recent, flat, recent, seasonal = [], [], [], [], [], []
    moved_a, moved_aware, moved_aware_recent, moved_flat, moved_recent, moved_seasonal = [], [], [], [], [], []
    for s, cut, ref, base in fitted:
        beta = model.beta(s.category)
        tail = statistics.mean(s.units[max(0, cut - 28):cut])
        # as deployed, the AI's base rate is the recent rate of sale at the prices those days had, not an all-history average
        recent_base = statistics.mean(u / ((p / ref) ** beta) for p, u in zip(s.price[max(0, cut - 28):cut], s.units[max(0, cut - 28):cut]))
        for k in range(cut, len(s.days)):
            ratio = s.price[k] / ref
            pa = base * (ratio ** beta)
            pr = recent_base * (ratio ** beta)
            ps = s.units[k - 7 * ((k - cut) // 7 + 1)] if k - 7 * ((k - cut) // 7 + 1) >= 0 else base          # same weekday in the last week of training
            for lst, val in ((actual, s.units[k]), (aware, pa), (aware_recent, pr), (flat, base), (recent, tail), (seasonal, ps)):
                lst.append(val)
            if abs(ratio - 1.0) >= MOVED:
                for lst, val in ((moved_a, s.units[k]), (moved_aware, pa), (moved_aware_recent, pr), (moved_flat, base), (moved_recent, tail), (moved_seasonal, ps)):
                    lst.append(val)
    out = {
        "series_used": len(fitted), "test_days": len(actual),
        "betas": {c: round(model.beta(c), 3) for c in sorted({s.category for s, _, _, _ in fitted})},
        "wape_all_days": {"price_aware": round(_wape(actual, aware), 4), "price_aware_recent_level": round(_wape(actual, aware_recent), 4), "average": round(_wape(actual, flat), 4),
                          "recent_average": round(_wape(actual, recent), 4), "same_weekday_last_week": round(_wape(actual, seasonal), 4)},
        "days_with_price_move": len(moved_a),
    }
    if moved_a:
        out["wape_price_move_days"] = {"price_aware": round(_wape(moved_a, moved_aware), 4), "price_aware_recent_level": round(_wape(moved_a, moved_aware_recent), 4),
                                       "average": round(_wape(moved_a, moved_flat), 4),
                                       "recent_average": round(_wape(moved_a, moved_recent), 4), "same_weekday_last_week": round(_wape(moved_a, moved_seasonal), 4)}
        best_baseline = min(out["wape_price_move_days"][k] for k in ("average", "recent_average", "same_weekday_last_week"))
        mv = out["wape_price_move_days"]
        # the same model with and without price, level for level: what price awareness adds by itself (positive: error is lower with it)
        out["price_awareness_gain_on_price_move_days"] = {
            "fixed_level_vs_average": round(1 - mv["price_aware"] / mv["average"], 4),
            "recent_level_vs_recent_average": round(1 - mv["price_aware_recent_level"] / mv["recent_average"], 4)}
        # the verdict is about the model as the AI uses it (recent level); the fixed-level form is reported beside it
        out["verdict"] = ("The price-aware model (recent level) beat every price-blind baseline on the days the price moved."
                          if mv["price_aware_recent_level"] < (1 - MIN_IMPROVEMENT) * best_baseline
                          else "The price-aware model did NOT clearly beat the best price-blind baseline on the days the price moved in this data set.")
    return out


def validate_demand(mix: "datasets.Mix", log=print) -> dict:
    result = {"kind": "demand", "datasets": mix.as_dict(), "by_dataset": {}}
    for ds in mix.ids():
        series = SERIES_LOADERS[ds]()
        r = backtest_price_model(series)
        r["series_loaded"] = len(series)
        result["by_dataset"][ds] = r
        log(f"{ds}: {r['series_used']} products tested of {len(series)} loaded")
        if r.get("wape_all_days"):
            log(f"   error (WAPE, lower is better), all test days: {r['wape_all_days']}")
        if r.get("wape_price_move_days"):
            log(f"   on the {r['days_with_price_move']} days with a price move: {r['wape_price_move_days']}")
            log("   price awareness on its own, like for like: " + str(r["price_awareness_gain_on_price_move_days"]))
            log("   " + r["verdict"])
        elif r.get("note"):
            log("   " + r["note"])
    result["note"] = ("Real shoppers, not our simulated ones. The data sets are not Philippine unless the file is yours; they test the method. "
                      "WAPE is total absolute error over total units on days the model has not seen.")
    return result


# ---- Customer Mission against what shoppers said --------------------------------------------------------------------------
def _norm_mission(text: str):
    t = (text or "").strip().lower().replace("_", " ").replace("-", " ")
    for m in ms.MISSIONS:
        if t == m.lower().replace("-", " "):
            return m
    return None


def validate_missions(answers_path=None, receipts_path=None) -> dict:
    """Join the till answers to the receipts by receipt id, classify each basket from its shape alone, and compare."""
    answers_path = Path(answers_path) if answers_path else datasets.folder("till-survey") / "answers.csv"
    base = datasets.folder("store-pos")
    receipts_path = Path(receipts_path) if receipts_path else next((base / n for n in ("receipts.csv", "sales.csv", "pos.csv") if (base / n).is_file()), None)
    if receipts_path is None:
        raise datasets.SelectionError("missions: the answers are matched to receipts, so store-pos/receipts.csv is needed too")
    answers = {}
    with answers_path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        norm = {h.strip().lower().replace(" ", "_"): h for h in (rd.fieldnames or [])}
        rid = next((norm[n] for n in ("receipt_id", "receipt", "receipt_no") if n in norm), None)
        ans = next((norm[n] for n in ("mission", "answer", "reason") if n in norm), None)
        if not (rid and ans):
            raise datasets.SelectionError("till-survey: answers.csv needs receipt_id and mission columns")
        for r in rd:
            m = _norm_mission(r[ans])
            if m and r[rid]:
                answers[r[rid]] = m
    baskets = {}
    with receipts_path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        norm = {h.strip().lower().replace(" ", "_"): h for h in (rd.fieldnames or [])}
        col = lambda *names: next((norm[n] for n in names if n in norm), None)       # noqa: E731
        rid, item, when, qty, price = col("receipt_id", "receipt", "receipt_no"), col("sku", "product_id", "product", "item"), \
            col("datetime", "date_time", "timestamp", "time"), col("qty", "quantity", "units"), col("price", "unit_price")
        if not (rid and item and when):
            raise datasets.SelectionError("missions: receipts need receipt id, product and date/time columns")
        for r in rd:
            if r[rid] not in answers:
                continue
            b = baskets.setdefault(r[rid], {"hour": _hour(r[when]), "lines": set(), "units": 0.0, "value": 0.0})
            b["lines"].add(r[item])
            q = float(r[qty] or 1) if qty else 1.0
            b["units"] += q
            b["value"] += q * float(r[price] or 0) if price else 0.0
    values = [b["value"] for b in baskets.values() if b["value"] > 0]
    median_value = statistics.median(values) if values else 0.0
    pairs, confusion = [], defaultdict(Counter)
    for rid, b in baskets.items():
        pred = ms.classify(ms.Basket(b["hour"], len(b["lines"]), b["units"], b["value"], False), median_value)
        truth = answers[rid]
        pairs.append((truth, pred))
        confusion[truth][pred] += 1
    if not pairs:
        return {"kind": "missions", "baskets_matched": 0, "note": "no answer could be matched to a receipt"}
    hits = sum(1 for t, p in pairs if t == p)
    majority = Counter(t for t, _ in pairs).most_common(1)[0]
    return {"kind": "missions", "baskets_matched": len(pairs), "answers_total": len(answers), "agreement": round(hits / len(pairs), 3),
            "always_guess_the_commonest_answer": round(majority[1] / len(pairs), 3), "commonest_answer": majority[0],
            "confusion": {t: dict(c) for t, c in confusion.items()},
            "note": "The classifier sees only the hour, number of lines, units and value of each basket (it cannot tell perishables from this file). "
                    "Agreement is exact match with the shopper's own answer."}


def _hour(text: str) -> int:
    text = (text or "").strip()
    for sep in ("T", " "):
        if sep in text:
            digits = text.split(sep, 1)[1].split(":")[0]
            return int(digits) % 24 if digits.isdigit() else 12
    return 12


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="simpeso.validate")
    ap.add_argument("kind", choices=["demand", "missions"])
    ap.add_argument("--datasets", default=None, help="the data set(s) to check against (required; see  python -m simpeso.datasets)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    try:
        mix = datasets.choose(args.datasets, args.kind)
        result = validate_demand(mix) if args.kind == "demand" else validate_missions()
        if args.kind == "missions":
            result["datasets"] = mix.as_dict()
    except datasets.SelectionError as e:
        print("Cannot start the test: " + str(e), file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else RUNS / f"validation-{args.kind}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    if args.kind == "missions":
        print(json.dumps({k: v for k, v in result.items() if k != "confusion"}, indent=1))
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

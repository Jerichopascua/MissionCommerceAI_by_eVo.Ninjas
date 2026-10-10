"""Real baskets as the source of simulated visits.

Loaders turn a data set's files into plain baskets (an optional hour, and (item, quantity) lines). A ReplaySource gives a visit one of those baskets:
the dataset's items are mapped onto the company's catalog by share of purchases, so the shape of real baskets survives (how many lines, how many
units, which items travel together) while the product identities are the shop's own. The basket then goes through the shopper's reaction to the
prices in force (behavior.respond_to_prices), so a test of the AI still has customers who respond to the AI's prices; that reaction stays the
simulator's own assumption and is not taken from the data. A MixSource picks, for every visit, one source by the weights the test chose."""
import csv
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import behavior, datasets, rng

MAX_BASKETS = 50_000
MAX_LINES = 12
MAX_QTY = 6


@dataclass(frozen=True)
class Basket:
    hour: int          # 0 to 23, or -1 when the data set has no time of day
    lines: tuple       # ((item key, quantity), ...)


def _pick(header: list, names: tuple):
    low = {h.strip().lower().replace(" ", "_").replace("-", "_"): h for h in header}      # "Receipt No" matches receipt_no
    for n in names:
        if n in low:
            return low[n]
    return None


def _hour_of(text: str) -> int:
    text = (text or "").strip()
    for sep in ("T", " "):
        if sep in text:
            part = text.split(sep, 1)[1]
            digits = part.split(":")[0]
            return int(digits) % 24 if digits.isdigit() else -1
    return -1


def _group(rows, receipt_key, hour_key, item_key, qty_key, limit) -> list:
    by = {}
    hours = {}
    for r in rows:
        rid = r.get(receipt_key)
        if rid is None or rid == "":
            continue
        if rid not in by and len(by) >= limit:
            continue
        item = r.get(item_key)
        if item in (None, ""):
            continue
        try:
            qty = float(r.get(qty_key) or 1)
        except ValueError:
            qty = 1.0
        qty = max(1, min(MAX_QTY, int(round(qty)))) if qty > 0 else 0
        if qty == 0:
            continue
        lines = by.setdefault(rid, Counter())
        lines[item] += qty
        if hour_key and rid not in hours:
            hours[rid] = _hour_of(r.get(hour_key))
    return [Basket(hours.get(rid, -1), tuple(c.items())) for rid, c in by.items() if c]


def load_store_pos(path=None, limit: int = MAX_BASKETS) -> list:
    """A real store's receipts: one row per line. Column names are matched loosely (receipt/sale/invoice/transaction id; datetime/date/time;
    sku/product/item/barcode; qty/quantity/units)."""
    base = datasets.folder("store-pos")
    path = Path(path) if path else next((base / n for n in ("receipts.csv", "sales.csv", "pos.csv") if (base / n).is_file()), None)
    if path is None or not path.is_file():
        raise datasets.SelectionError("store-pos: no receipts.csv in " + str(base))
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        h = rd.fieldnames or []
        rid = _pick(h, ("receipt_id", "receipt", "receipt_no", "sale_id", "invoice", "invoice_no", "transaction_id", "basket_id", "order_id"))
        item = _pick(h, ("sku", "product_id", "product", "item", "item_code", "barcode", "product_code"))
        qty = _pick(h, ("qty", "quantity", "units"))
        when = _pick(h, ("datetime", "date_time", "timestamp", "sale_date", "time", "date"))
        if not (rid and item):
            raise datasets.SelectionError("store-pos: the file needs a receipt column and a product column (found: " + ", ".join(h) + ")")
        return _group(rd, rid, when, item, qty or "", limit)


def load_instacart(base=None, limit: int = MAX_BASKETS) -> list:
    base = Path(base) if base else datasets.folder("instacart")
    hours, wanted = {}, []
    with (base / "orders.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("eval_set", "prior") != "prior":
                continue
            wanted.append(r["order_id"])
            hours[r["order_id"]] = int(r["order_hour_of_day"])
            if len(wanted) >= limit:
                break
    keep = set(wanted)
    last = max((int(w) for w in wanted), default=0)
    by = {}
    with (base / "order_products__prior.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            oid = r["order_id"]
            if oid in keep:
                by.setdefault(oid, Counter())[r["product_id"]] += 1
            elif int(oid) > last and len(by) >= len(keep):
                break
    return [Basket(hours[o], tuple(c.items())) for o, c in by.items() if c]


def load_dunnhumby(base=None, limit: int = MAX_BASKETS) -> list:
    base = Path(base) if base else datasets.folder("dunnhumby")
    with (base / "transaction_data.csv").open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        up = {h.strip().upper(): h for h in (rd.fieldnames or [])}
        for need in ("BASKET_ID", "PRODUCT_ID", "QUANTITY"):
            if need not in up:
                raise datasets.SelectionError(f"dunnhumby: transaction_data.csv has no {need} column")
        rows = []
        seen = set()
        for r in rd:
            b = r[up["BASKET_ID"]]
            if b not in seen and len(seen) >= limit:
                continue
            seen.add(b)
            t = (r.get(up["TRANS_TIME"]) or "").strip() if "TRANS_TIME" in up else ""
            r["_hour"] = (int(t.zfill(4)[:2]) % 24) if t.isdigit() else -1
            rows.append(r)
    by, hours = {}, {}
    for r in rows:
        b = r[up["BASKET_ID"]]
        try:
            q = max(1, min(MAX_QTY, int(round(float(r[up["QUANTITY"]] or 1)))))
        except ValueError:
            q = 1
        by.setdefault(b, Counter())[r[up["PRODUCT_ID"]]] += q
        hours.setdefault(b, r["_hour"])
    return [Basket(hours[b], tuple(c.items())) for b, c in by.items() if c]


LOADERS = {"store-pos": load_store_pos, "instacart": load_instacart, "dunnhumby": load_dunnhumby}


def hour_profile(baskets: list) -> dict:
    """{hour: share} of the baskets that carry a time of day (empty when none do)."""
    c = Counter(b.hour for b in baskets if b.hour >= 0)
    n = sum(c.values())
    return {h: v / n for h, v in sorted(c.items())} if n else {}


def describe(baskets: list) -> dict:
    sizes = [len(b.lines) for b in baskets]
    units = [sum(q for _, q in b.lines) for b in baskets]
    items = Counter(i for b in baskets for i, _ in b.lines)
    return {"baskets": len(baskets), "distinct_items": len(items), "lines_per_basket": round(statistics.mean(sizes), 2) if sizes else 0,
            "units_per_basket": round(statistics.mean(units), 2) if units else 0, "has_time_of_day": bool(hour_profile(baskets))}


class ProductMapper:
    """Maps a data set's items onto catalog codes so each catalog product receives an equal share of the purchases, most-bought items first.
    The same item always lands on the same product, so items that travel together stay together."""

    def __init__(self, baskets: list, catalog_codes: list):
        freq = Counter()
        for b in baskets:
            for item, q in b.lines:
                freq[item] += q
        total = sum(freq.values()) or 1
        n = max(1, len(catalog_codes))
        self.map, running = {}, 0
        for item, count in sorted(freq.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            mid = (running + count / 2) / total              # the middle of this item's slice of all purchases
            self.map[item] = catalog_codes[min(n - 1, int(mid * n))]
            running += count

    def lines(self, basket: Basket) -> list:
        out = Counter()
        for item, q in basket.lines[:MAX_LINES * 2]:
            code = self.map.get(item)
            if code is not None:
                out[code] += q
        return list(out.items())[:MAX_LINES]


class ReplaySource:
    def __init__(self, dataset_id: str, baskets: list):
        if not baskets:
            raise datasets.SelectionError(f"{dataset_id}: no baskets could be read")
        self.id, self.baskets = dataset_id, baskets
        self._mappers = {}

    def _mapper(self, plan, company: str) -> ProductMapper:
        if company not in self._mappers:
            catalog = next(c for c in plan.companies if c.key == company).catalog
            self._mappers[company] = ProductMapper(self.baskets, [p.code for p in catalog])
        return self._mappers[company]

    def fill_basket(self, plan, visit, seed, price_ratio=None, calib=None):
        r = rng.derive(seed, "replay", self.id, visit.id)
        basket = self.baskets[r.randrange(len(self.baskets))]
        lines = self._mapper(plan, visit.company).lines(basket)
        return behavior.respond_to_prices(visit, lines, seed, price_ratio) if lines else None


class RulesSource:
    id = "simulated-rules"

    def fill_basket(self, plan, visit, seed, price_ratio=None, calib=None):
        return behavior.fill_basket(plan, visit, seed, price_ratio, calib)


class MixSource:
    """For every visit one source is picked by the weights of the mix (seeded: the same run repeats)."""

    def __init__(self, weights: dict, sources: dict):
        self.ids = list(weights)
        self.weights = [weights[i] for i in self.ids]
        self.sources = sources
        self.counts = Counter()

    def fill_basket(self, plan, visit, seed, price_ratio=None, calib=None):
        pick = rng.derive(seed, "datasets", visit.id).choices(self.ids, weights=self.weights)[0]
        self.counts[pick] += 1
        return self.sources[pick].fill_basket(plan, visit, seed, price_ratio, calib)


def build_source(mix: "datasets.Mix", log=print) -> MixSource:
    """Load what the chosen data sets need and return the object a business-day run takes its baskets from."""
    sources = {}
    for dataset_id in mix.ids():
        if dataset_id == "simulated-rules":
            sources[dataset_id] = RulesSource()
        else:
            baskets = LOADERS[dataset_id]()
            d = describe(baskets)
            log(f"  {dataset_id}: {d['baskets']} baskets, {d['distinct_items']} items, {d['lines_per_basket']} lines per basket")
            sources[dataset_id] = ReplaySource(dataset_id, baskets)
    return MixSource(mix.weights, sources)

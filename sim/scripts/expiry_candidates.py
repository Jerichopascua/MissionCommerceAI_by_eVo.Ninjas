"""Which products in a company's catalog are candidates for expiry-date tracking? Read-only: it only SELECTs and writes a CSV.

    python scripts/expiry_candidates.py --tenant 6                       # PesoWeb_MissionDev, writes sim/runs/expiry-candidates-tenant6.csv
    python scripts/expiry_candidates.py --tenant 6 --show 15

Real catalogs often have no useful category (most products are "NA"), so this works from the product NAME with an explicit, reviewable rule
list, in tiers by how fast the product expires. It is a worklist for a person to confirm, not a decision: a name can mislead (BREAD CRUMBS are
not bread, CHEESE-flavoured noodles are not cheese), so each rule is anchored on whole words and has exclusions.

  Tier 1  fresh or chilled: days to weeks. Watch these first; the AI's markdowns matter most here.
  Tier 2  short to medium: weeks to a few months (liquid milk and drinks, bread, cakes, snack bars, jelly, chips).
  Tier 3  packaged, with a best-before date months to years away (biscuits, noodles, canned goods, sauces, coffee, candy).
  Tier 4  medicine, vitamins, personal care: an expiry date that matters for safety or regulation.
  (anything else is not suggested: soap, detergent, wipes, tools, cigarettes...)"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEP = "\x1f"

QUERY = """SET NOCOUNT ON;
SELECT CAST(p.Id AS varchar(20)), REPLACE(ISNULL(p.ProductCode, ''), CHAR(31), ' '), REPLACE(p.ProductName, CHAR(31), ' '),
       CAST(ISNULL(p.Cost, 0) AS varchar(30)), CAST(ISNULL(p.Price, 0) AS varchar(30)), CAST(CASE WHEN p.MonitorExpiry = 1 THEN 1 ELSE 0 END AS varchar(2)),
       CAST(ISNULL(s.Qty, 0) AS varchar(30)), CAST(ISNULL(c.CategoryName, '') AS nvarchar(100))
FROM Products p
LEFT JOIN (SELECT ProductId, SUM(Quantity) AS Qty FROM ProductWarehouses GROUP BY ProductId) s ON s.ProductId = p.Id
LEFT JOIN Categories c ON c.Id = p.CategoryId
WHERE p.TenantID = {tenant}
ORDER BY p.ProductName"""

# (tier, label, pattern). First match wins; the order matters: exclusions first.
NOT_FOOD = re.compile(r"\b(SOAP|DET(ERGENT)?|PWD|POWDER DET|FBCN|FABRIC|WIPES?|COTTON|TAPE|SCISSOR|CANDLE|BAG|CUPS?|STRAW|STICKY|SCOURER|SPONGE|SCRUB|CIGARETTE|CAMEL|MARLBORO|"
                      r"MASK|NPKN|NAPKIN|SOFY|SISTERS|BAIT|KILLER|DISINFECTANT|CLEANER|DSHWSH|DISHWASH|SPRAY BOTTLE|BOARD|LIGHTER|BATTERY|FREEBIE|"
                      r"HAIR DYE|STYLING GEL|DEO|DEODORANT|REXONA|DEO-LTN|SILKA|SURF|SAFEGUARD|SFGD|PRIDE|BREEZE|ARIEL|TIDE|DOWNY)\b", re.I)

# Shelf-stable look-alikes that must never be taken for fresh produce, dairy or personal care.
SHELF_STABLE = re.compile(r"\b(CATSUP|KETCHUP|SAUCE|PASTE|SOUP|NOODLES?|RAMYUN|RAMEN|SAMYANG|BULDAK|SHIN|CUP|SNACK|CHIPS|SPREAD|CORNED|BISCUITS?|HANSEL|CRACKERS?|WAFER|COOKIES?|"
                          r"COFFEE|SAN ?MIG \d|CEREAL|OATS|QUAKER|COCOMILK|COCONUT MILK|COCO MILK)\b", re.I)

RULES = [
    # --- tier 1: fresh or chilled (only names that are clearly fresh or chilled)
    (1, "liquid milk or yoghurt drink", re.compile(r"\b(FRESH MILK|YAKULT|YOGURT|YOGHURT|KEFIR|CHOCOLATE MILK|CHOCO MILK|CHOCOLATE DRINK|SOYMILK|SOY MILK)\b", re.I)),
    (1, "chilled meat", re.compile(r"\b(TAPA|DRUMMETS?|NUGGETS|SISIG|HAM|BACON|HOTDOG|HOT DOG|TOCINO|LONGGANISA|SAUSAGE|PORK|CHICKEN BREAST|MEATBALL|BURGER PATTY|FROZEN)\b", re.I)),
    (1, "fresh produce, eggs or tofu", re.compile(r"\b(SIBUYAS|ONION|TOMATO|EGG|EGGS|ITLOG|TOKWA|TOFU|KANGKONG|CABBAGE|CARROT|POTATO|BANANA|SALAD MACARONI)\b", re.I)),
    (1, "fresh bread or pastry", re.compile(r"\b(PANDESAL|LOAF|TOASTED BREAD|TASTY BREAD|PAN DE|ENSAYMADA)\b", re.I)),
    (1, "margarine, butter or cheese", re.compile(r"\b(MARGARINE|BUTTER|PARMESAN|QUICK MELT|EDEN CHEESE|CHEESE SLICES?|CREAM CHEESE)\b", re.I)),
    # --- tier 4: medicine, vitamins, personal care
    (4, "medicine or health product", re.compile(r"\b(BIOGESIC|STREPSILS|SALONPAS|VITAMIN|VIT-C|VIT C|PARACETAMOL|IBUPROFEN|NEOZEP|BIOFLU|DECOLGEN|MEDICOL|ALAXAN|MUCONASE|SENSODYNE|SENSODINE|"
                                                 r"LAGUNDI|OINTMENT|TABLET|CAPSULE|SYRUP|ANTACID|KREMIL|CEELIN|PASTILLES|LOZENGE|THERMOMETER)\b", re.I)),
    (4, "personal care with a shelf life", re.compile(r"\b(LOTION|SHMP|SHAMPOO|CONDITIONER|TOOTHPASTE|SUNSCREEN|LIPSTICK|SERUM|MOISTURI[SZ]ER|WHITENING|FACE CREAM|HAND CREAM|BODY CREAM)\b", re.I)),
    # --- tier 2: weeks to a few months
    (2, "packaged cake, cookies, brownies or donuts", re.compile(r"\b(DONUT|DOOWEE|WHOOPEE|WHOOPIE|MALLOW CAKE|BROWNIE|BROWNIES|MUFFIN|CUPCAKES?|SWISS ROLL|QUAKE OVERLOAD|CAKES?)\b", re.I)),
    (2, "milk drink or juice", re.compile(r"\b(MILK|JUICE|NECTAR|TETRA|MILO|OVALTINE|BEAR BRAND|ALASKA|NESQUIK)\b", re.I)),
    (2, "jelly, nata or pudding", re.compile(r"\b(JELLY|NATA|PUDDING|NATA DE COCO)\b", re.I)),
    # --- tier 3: best-before months or years away
    (3, "biscuit, cracker, cookie or wafer", re.compile(r"\b(BISCUIT|BISCUITS|CRACKERS?|CRCKR|CRCKRS|CRKR|WAFER|WAFERTIME|WAFERTME|SKY ?FLAKES|HANSEL|REBISCO|MARIE|FLAT TOPS|SUPERSTIX|BRAVO|COOKIES?)\b", re.I)),
    (3, "chips or snack", re.compile(r"\b(CHIPS|PRINGLES|POPCORN|CHICHARON|PEANUTS?|NUTS|SNACKU|TORTILLA|VEGETABLE SNACK|SNACK)\b", re.I)),
    (3, "instant noodles, pasta or sauce", re.compile(r"\b(RAMYUN|RAMEN|NOODLES?|SPAGHETTI|SUPERGHETTI|BIHON|BIHUN|PANCIT|MACARONI|SAMYANG|BULDAK|SOUPER MEAL|SHIN|CUP)\b", re.I)),
    (3, "canned or preserved food", re.compile(r"\b(CORNED|SARDINES?|TUNA|MACKEREL|SQUID|SPAM|LUNCHEONMEAT|LUNCHEON MEAT|LMEAT|ULAM|LIVER SPREAD|VIENNA|BEANS|KERNEL CORN|MUSHROOM|RAISINS|"
                                              r"SHIITAKE|SOUP BASE|SAGO|COCOMILK|COCONUT MILK|COCO MILK)\b", re.I)),
    (3, "soft drink, energy drink or beer", re.compile(r"\b(SPRITE|COKE|COCA|ROYAL TRU|PEPSI|MIRINDA|SPEED BAR|STING|CIFRUS|GATORADE|RED HORSE|SAN MIGUEL|BEER|VODKA|MULE|RITE N.?LITE|SODA|BEVERAGE)\b", re.I)),
    (3, "sauce, oil or condiment", re.compile(r"\b(SOY ?SAUCE|VINEGAR|SUKA|PATIS|SAUCE|CATSUP|KETCHUP|OIL|SEASONING|SPICES?|CHILI|GARLIC|SESAME|ACCORD|SIBOT|CASUBHA|MIX|FLOUR|CORNSTARCH|BAKING SODA|BREAD CRUMBS?|SALT|SPREAD)\b", re.I)),
    (3, "coffee, tea, cereal or candy", re.compile(r"\b(COFFEE|KAPE|TEA|OATS|QUAKER|CEREAL|CANDY|CANDIES|CHOCOLATE|CHOCO|SAN ?MIG \d|SANMIG|NESCAFE|CREAMER|SUGAR|TEMPURA|FLAKES)\b", re.I)),
]

TIER_NAMES = {1: "Tier 1 fresh or chilled", 2: "Tier 2 short to medium shelf life", 3: "Tier 3 packaged, best-before date", 4: "Tier 4 medicine and personal care"}


def classify(name: str):
    """(tier, why) or None. Non-food household goods are excluded first; the first matching rule wins."""
    if NOT_FOOD.search(name) and not re.search(r"\b(BIOGESIC|STREPSILS|SALONPAS)\b", name, re.I):
        return None
    for tier, why, pat in RULES:
        if pat.search(name):
            if tier in (1, 2, 4) and SHELF_STABLE.search(name) and why not in ("liquid milk or yoghurt drink", "margarine, butter or cheese", "medicine or health product"):
                continue                      # e.g. banana catsup is not produce, cream of mushroom soup is not cream, Shin kimchi is noodles
            return tier, why
    return None


def fetch(tenant: int, database: str, server: str) -> list:
    res = subprocess.run(["sqlcmd", "-S", server, "-d", database, "-E", "-h", "-1", "-W", "-s", SEP, "-b", "-Q", QUERY.format(tenant=int(tenant))],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise SystemExit(res.stdout.strip() or res.stderr.strip())
    rows = []
    for line in res.stdout.splitlines():
        p = line.rstrip("\r\n").split(SEP)
        if len(p) != 8 or not p[0].strip().isdigit():
            continue
        rows.append({"id": int(p[0]), "code": p[1].strip(), "name": p[2].strip(), "cost": float(p[3]), "price": float(p[4]),
                     "tracked": p[5].strip() == "1", "stock": float(p[6]), "category": p[7].strip()})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, required=True)
    ap.add_argument("--database", default="PesoWeb_MissionDev")
    ap.add_argument("--server", default=r"(localdb)\MSSQLLocalDB")
    ap.add_argument("--out", default=None)
    ap.add_argument("--show", type=int, default=12, help="how many products per tier to print")
    args = ap.parse_args(argv)
    rows = fetch(args.tenant, args.database, args.server)
    out = Path(args.out) if args.out else ROOT / "runs" / f"expiry-candidates-tenant{args.tenant}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    picked = []
    for r in rows:
        c = classify(r["name"])
        if c:
            r["tier"], r["why"] = c
            r["value"] = round(r["stock"] * r["cost"], 2)
            picked.append(r)
    picked.sort(key=lambda r: (r["tier"], -r["value"], r["name"]))
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tier", "why", "product_id", "code", "name", "cost", "price", "tracked_now", "stock", "stock_value_at_cost"])
        for r in picked:
            w.writerow([r["tier"], r["why"], r["id"], r["code"], r["name"], r["cost"], r["price"], "yes" if r["tracked"] else "no", r["stock"], r["value"]])
    total = len(rows)
    print(f"{total} products in company {args.tenant}; {sum(1 for r in rows if r['tracked'])} have expiry tracking on now.")
    print(f"{len(picked)} look like candidates ({total - len(picked)} do not: soap, detergent, tools, cigarettes and the like).\n")
    for tier in (1, 2, 3, 4):
        group = [r for r in picked if r["tier"] == tier]
        if not group:
            continue
        untracked = [r for r in group if not r["tracked"]]
        print(f"{TIER_NAMES[tier]}: {len(group)} products, {len(untracked)} not yet tracked, about {sum(r['value'] for r in group):,.0f} pesos at cost on the shelf")
        for r in group[: args.show]:
            print(f"   {r['name'][:46]:46s} {r['why'][:30]:30s} stock {r['stock']:6.0f}  cost {r['cost']:7.2f}  at cost {r['value']:9,.0f}" + ("  [tracked]" if r["tracked"] else ""))
        if len(group) > args.show:
            print(f"   ... and {len(group) - args.show} more in the CSV")
        print()
    print(f"Full list: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

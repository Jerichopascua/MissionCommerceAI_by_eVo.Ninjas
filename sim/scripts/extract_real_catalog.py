"""Extract the REAL product catalog (name, cost, price, barcode) and real sales concentration from a restored PesoWeb
database, read-only, for use as the simulator's catalog.

    python scripts/extract_real_catalog.py --db PesoWeb_V2_Real --tenants 6,17

Writes sim/runs/real_catalog.json (git-ignored: it is a real business's product list and prices; never commit it).
Rows that look like test data, or that have no real cost and price (price must exceed cost), are dropped."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQLCMD = r"D:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE"


def query(db: str, sql: str) -> list:
    out = subprocess.run([SQLCMD, "-S", r"(localdb)\MSSQLLocalDB", "-E", "-C", "-d", db, "-h", "-1", "-W", "-s", "\t", "-w", "4000", "-Q", "SET NOCOUNT ON; " + sql],
                         capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="PesoWeb_V2_Real")
    ap.add_argument("--tenants", default="6,17")
    args = ap.parse_args(argv)
    tenants = ",".join(str(int(t)) for t in args.tenants.split(","))
    rows = query(args.db, f"SELECT Id, ISNULL(ProductCode,''), ProductName, Cost, Price FROM Products WHERE TenantID IN ({tenants}) "
                          f"AND Cost>0 AND Price>Cost AND ProductName NOT LIKE '%TEST%' AND ProductName NOT LIKE 'SAMPLE%' ORDER BY Id")
    sold = {int(r[0]): float(r[1]) for r in query(args.db, f"SELECT d.ProductId, SUM(d.Quantity) FROM SaleDetails d JOIN Sales s ON s.Id=d.SaleId WHERE s.TenantID IN ({tenants}) GROUP BY d.ProductId")}
    seen, items = set(), []
    for pid, code, name, cost, price in rows:
        name = name.strip()
        if not name or name.upper() in seen:
            continue
        seen.add(name.upper())
        items.append({"code": (code.strip() or f"REAL-{int(pid):05d}")[:20], "name": name[:100], "cost": float(cost), "price": float(price), "sold_units": sold.get(int(pid), 0.0)})
    mx = max((i["sold_units"] for i in items), default=0) or 1.0
    for i in items:                                            # sales concentration: never-sold SKUs stay possible, best sellers dominate
        i["popularity"] = round(0.2 + 8.0 * i["sold_units"] / mx, 3)
    codes = {}
    for i in items:                                            # product codes must be unique inside a tenant
        codes[i["code"]] = codes.get(i["code"], 0) + 1
        if codes[i["code"]] > 1:
            i["code"] = f"{i['code'][:14]}-{codes[i['code']]}"
    out = ROOT / "runs" / "real_catalog.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"source_db": args.db, "tenants": tenants, "items": items}, indent=1), encoding="utf-8")
    sold_items = sum(1 for i in items if i["sold_units"] > 0)
    print(json.dumps({"products": len(items), "with_real_sales": sold_items, "wrote": "sim/runs/real_catalog.json"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

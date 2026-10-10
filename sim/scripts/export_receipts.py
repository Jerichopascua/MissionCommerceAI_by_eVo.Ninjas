"""Export one company's completed sales from PesoWeb's own tables into the receipts file the store-pos customer data set reads.

    python scripts/export_receipts.py --tenant 6                     # from PesoWeb_MissionDev (the default)
    python scripts/export_receipts.py --tenant 6 --database PesoWeb_V2_Real --out customer_data/store-pos/receipts.csv

Read-only (SELECT only). One row per sold line: receipt id, date and time, product code, quantity, selling price, category. The receipt id is a
short hash of the company and sale number, so receipts of one shopper stay together but nothing can be traced back; customers, cashiers, names,
phone numbers and payment details are never exported. Only completed sales (OrderStatus 1) are included.
The output folder (sim/customer_data/) is git-ignored."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso import datasets      # noqa: E402

SEP = "\x1f"        # unit separator: cannot occur in product codes or category names (it is stripped below), unlike commas or bars

QUERY = """SET NOCOUNT ON;
SELECT CAST(s.Id AS varchar(20)), CONVERT(varchar(19), s.SaleDate, 120), REPLACE(REPLACE(ISNULL(p.ProductCode, CAST(p.Id AS varchar(20))), CHAR(31), ' '), CHAR(13), ' '),
       CAST(d.Quantity AS varchar(30)), CAST(ISNULL(d.SalePrice, d.Price) AS varchar(30)), REPLACE(REPLACE(ISNULL(c.CategoryName, 'NA'), CHAR(31), ' '), CHAR(13), ' ')
FROM Sales s
JOIN SaleDetails d ON d.SaleId = s.Id
JOIN Products p ON p.Id = d.ProductId
LEFT JOIN Categories c ON c.Id = p.CategoryId
WHERE s.TenantID = {tenant} AND s.OrderStatus = 1 AND d.Quantity > 0
ORDER BY s.SaleDate, s.Id, d.Id"""


def receipt_id(tenant: int, sale_id: str) -> str:
    return hashlib.sha256(f"{tenant}:{sale_id}".encode("utf-8")).hexdigest()[:10]


def to_csv_lines(raw_lines: list, tenant: int) -> list:
    """sqlcmd output lines (fields separated by SEP) -> CSV lines with a header. Lines that are not data rows are skipped."""
    out = ["receipt_id,datetime,sku,qty,price,category"]
    for line in raw_lines:
        parts = line.rstrip("\r\n").split(SEP)
        if len(parts) != 6 or not parts[1][:4].isdigit():
            continue
        sale_id, when, sku, qty, price, cat = (p.strip() for p in parts)
        out.append(",".join([receipt_id(tenant, sale_id), when, '"' + sku.replace('"', "'") + '"', qty, price, '"' + cat.replace('"', "'") + '"']))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, required=True, help="the company (TenantID) whose sales to export")
    ap.add_argument("--database", default="PesoWeb_MissionDev")
    ap.add_argument("--server", default=r"(localdb)\MSSQLLocalDB")
    ap.add_argument("--out", default=None, help="default: customer_data/store-pos/receipts.csv")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else datasets.folder("store-pos") / "receipts.csv"
    res = subprocess.run(["sqlcmd", "-S", args.server, "-d", args.database, "-E", "-h", "-1", "-W", "-s", SEP, "-b", "-Q", QUERY.format(tenant=int(args.tenant))],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(res.stdout.strip() or res.stderr.strip(), file=sys.stderr)
        return 1
    lines = to_csv_lines(res.stdout.splitlines(), args.tenant)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    receipts = len({l.split(",", 1)[0] for l in lines[1:]})
    print(f"{len(lines) - 1} lines on {receipts} receipts written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

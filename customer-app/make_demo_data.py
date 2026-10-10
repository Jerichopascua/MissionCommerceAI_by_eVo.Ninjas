"""Builds data.json (demo catalog and demo customers) and the app icons. Demo only: the real app reads this from PesoWeb.

    python make_demo_data.py
"""
import csv
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CSV = HERE.parent / "sim" / "runs" / "expiry-candidates-tenant6.csv"
ART = Path("D:/git/Retailo_v1_mission/ClientApp/src/assets/images/dmall")

# product id -> (kind, percent off, days left of the offer, note)
OFFERS = {
    "1404": ("sale", 20, 5, "Weekend sale"),
    "1468": ("sale", 15, 5, "Weekend sale"),
    "1406": ("sale", 25, 3, "Weekend sale"),
    "1362": ("clearance", 50, 2, "Best before soon - rush to the store"),
    "1421": ("clearance", 45, 2, "Best before soon - rush to the store"),
    "1393": ("clearance", 40, 1, "Last day"),
    "1485": ("sale", 18, 6, "Sale"),
    "1012": ("sale", 12, 7, "Sale"),
    "1401": ("sale", 10, 7, "Sale"),
    "1385": ("clearance", 35, 3, "Clearance"),
    "1066": ("clearance", 30, 3, "Clearance"),
}


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    pick = []
    for tier, n in (("1", 8), ("2", 8), ("3", 14)):
        pick += [r for r in rows if r["tier"] == tier and 8 <= float(r["price"]) <= 300][:n]
    for pid in OFFERS:                                   # make sure every offer product is in the list
        if not any(p["product_id"] == pid for p in pick):
            pick += [r for r in rows if r["product_id"] == pid][:1]
    products = []
    for r in pick:
        o = OFFERS.get(r["product_id"])
        p = {"id": int(r["product_id"]), "name": r["name"].title().replace("Purefoods", "Purefoods"), "price": float(r["price"])}
        if o:
            p["offer"] = {"kind": o[0], "percentOff": o[1], "daysLeft": o[2], "note": o[3]}
        products.append(p)
    data = {
        "store": {"name": "520 Minimart", "phone": "0917 000 0520", "hours": "7:00 AM - 10:00 PM"},
        "products": products,
        "customers": [
            {"userId": "juan", "phone": "09171234567", "password": "demo123", "name": "Juan Dela Cruz", "email": "juan@example.test",
             "owes": [{"ref": "INV-2031", "description": "Groceries on account", "amount": 1250.0, "dueInDays": 4},
                      {"ref": "INV-1988", "description": "Rice and cooking oil", "amount": 780.5, "dueInDays": -3}]},
            {"userId": "maria", "phone": "09181234567", "password": "demo123", "name": "Maria Santos", "email": "",
             "owes": []},
        ],
    }
    (HERE / "data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    # app icons: the DMALL store icon on the pale background
    src = Image.open(ART / "icon-bag-chart.png").convert("RGBA")
    for size in (192, 512):
        canvas = Image.new("RGBA", (size, size), (238, 244, 255, 255))
        icon = src.copy()
        icon.thumbnail((int(size * 0.62), int(size * 0.62)))
        canvas.alpha_composite(icon, ((size - icon.width) // 2, (size - icon.height) // 2))
        canvas.convert("RGB").save(HERE / "icons" / f"icon-{size}.png")
    for name in ("hub-banner-clearance", "icon-diamond"):
        Image.open(ART / f"{name}.png").save(HERE / "icons" / f"{name}.png")
    print(len(products), "products,", sum(1 for p in products if "offer" in p), "on offer")


if __name__ == "__main__":
    main()

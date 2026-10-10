"""Builds data.json (the saved prices used offline, plus the demo customers) and the app icons. Run with PesoWeb up so the saved prices are current.

    python make_demo_data.py
"""
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ART = Path("D:/git/Retailo_v1_mission/ClientApp/src/assets/images/dmall")

def titlecase(s):
    import re
    return re.sub(r"(^|[\s(\-/])([a-z])", lambda m: m.group(1) + m.group(2).upper(), s.lower())


def products_from_pesoweb():
    """The store's current prices and offers, as the customer app downloads them (the saved copy used when offline)."""
    import urllib.request
    with urllib.request.urlopen("http://localhost:5071/api/customer-app/offers", timeout=30) as r:
        feed = json.load(r)
    out = []
    for p in feed["products"]:
        item = {"id": p["id"], "name": titlecase(p["name"]), "price": p["price"]}
        o = p.get("offer")
        if o:
            item["offer"] = {"kind": o["kind"], "percentOff": o["percentOff"], "price": o["price"], "daysLeft": o["daysLeft"], "note": o["note"]}
        out.append(item)
    return out


def main():
    products = products_from_pesoweb()
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
    for name in ("icon-diamond",):
        Image.open(ART / f"{name}.png").save(HERE / "icons" / f"{name}.png")
    print(len(products), "products,", sum(1 for p in products if "offer" in p), "on offer")


if __name__ == "__main__":
    main()

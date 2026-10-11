"""Live check of the customer app's own accounts against the running PesoWeb (company named in CustomerApp:TenantId):
a first-time shopper registers, logs in with the phone number or the user ID, changes phone and password, and sees the store's message
when a manager puts a product on sale and tells the registered customers.

    python scripts/customer_app_check.py
It registers one test shopper and removes it again at the end (set KEEP=1 to keep it).
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import PesoWebDriver            # noqa: E402

BASE = "http://localhost:5071"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:200].decode("utf-8", "replace")}


def sql(q):
    subprocess.run(["sqlcmd", "-S", r"(localdb)\MSSQLLocalDB", "-d", "PesoWeb_MissionDev", "-E", "-b", "-Q", q], check=True, capture_output=True)


def main() -> int:
    phone = "0999" + str(random.randint(1000000, 9999999))
    user = "check" + str(random.randint(1000, 9999))
    new_phone = "0998" + str(random.randint(1000000, 9999999))

    print("1. A first-time shopper registers")
    st, b = call("POST", "/api/customer-app/register", {"name": "Check Shopper", "phone": phone, "password": "abc123", "userId": user})
    check(st == 200 and b.get("token") and b["profile"]["name"] == "Check Shopper", f"registered: {st}")
    token = b.get("token")
    st, b2 = call("POST", "/api/customer-app/register", {"name": "Someone", "phone": phone, "password": "abc123"})
    check(st == 409, "the same phone number cannot register twice")
    st, b2 = call("POST", "/api/customer-app/register", {"name": "X", "phone": "123", "password": "abc"})
    check(st == 400, "a bad name, number and password are refused")

    print("2. Log in with the phone number or the user ID")
    st, b = call("POST", "/api/customer-app/login", {"who": phone, "password": "abc123"})
    check(st == 200 and b["profile"]["userId"] == user, "login by phone number")
    st, b = call("POST", "/api/customer-app/login", {"who": user.upper(), "password": "abc123"})
    check(st == 200, "login by user ID")
    st, b = call("POST", "/api/customer-app/login", {"who": phone, "password": "wrong"})
    check(st == 401, "a wrong password is refused")

    print("3. Profile: phone and password can change, the user ID cannot")
    st, me = call("GET", "/api/customer-app/me", token=token)
    check(st == 200 and me["userId"] == user, "the profile is returned for the signed-in shopper")
    st, _ = call("GET", "/api/customer-app/me")
    check(st == 401, "no token, no profile")
    st, _ = call("PUT", "/api/customer-app/me", {"phone": new_phone, "currentPassword": "nope"}, token)
    check(st == 400, "changing the phone needs the current password")
    st, me = call("PUT", "/api/customer-app/me", {"phone": new_phone, "currentPassword": "abc123", "newPassword": "newpass1"}, token)
    check(st == 200 and me["phone"] == new_phone and me["userId"] == user, "phone and password changed, user ID unchanged")
    st, _ = call("POST", "/api/customer-app/login", {"who": new_phone, "password": "newpass1"})
    check(st == 200, "login works with the new phone number and password")

    print("4. The store tells its registered customers about a sale")
    drv = PesoWebDriver(BASE, "customer-app-check")
    a = drv.login("superuser@520minimart.test", "Abc123##")
    st, products = drv._call("GET", "/api/inventory/products?searchValue=CHILI POWDER&pageSize=10&page=1", a.token, raw=True)
    pid = next(p["id"] for p in products["data"] if "ROBINSONS CHILI" in p["productName"].upper())
    ends = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    st, sale = drv._call("POST", "/api/product-sales", a.token,
                         json_body={"productId": pid, "percentOff": 12, "endsOn": ends, "note": "check", "notify": True}, raw=True)
    check(st == 200 and sale.get("notified", 0) >= 1, f"put on sale and told {sale.get('notified')} registered customer(s)")
    st, msgs = call("GET", "/api/customer-app/messages")
    check(st == 200 and any("CHILI" in m["title"].upper() for m in msgs), "the shopper's app lists the message")
    if st == 200:
        drv._call("POST", f"/api/product-sales/{sale['id']}/end", a.token, json_body={}, raw=True)

    print("5. A reservation made in the app is what the cashier sees")
    st, products = drv._call("GET", "/api/inventory/products?searchValue=CHOCO MUCHO&pageSize=10&page=1", a.token, raw=True)
    mucho = next(p for p in products["data"] if "CHOCO MUCHO" in p["productName"].upper())
    st, sale2 = drv._call("POST", "/api/product-sales", a.token,
                          json_body={"productId": mucho["id"], "percentOff": 50, "endsOn": ends, "note": "check", "notify": False}, raw=True)
    st, res = call("POST", "/api/customer-app/reserve", {"lines": [{"productId": mucho["id"], "quantity": 3}]}, token)
    check(st == 200 and res.get("code", "").startswith("R") and abs(res.get("total", 0) - 15.0) < 0.01, f"reserved 3 at the sale price, code {res.get('code')}, total {res.get('total')}")
    st, _ = call("POST", "/api/customer-app/reserve", {"lines": [{"productId": mucho["id"], "quantity": 1}]})
    check(st == 401, "a reservation needs a signed-in shopper")
    st, mine = call("GET", "/api/customer-app/reservations", token=token)
    check(st == 200 and mine and mine[0]["code"] == res["code"], "the shopper sees it in My reservations")
    st, order = drv._call("GET", f"/api/online-orders/{res['code']}", a.token, raw=True)
    check(st == 200 and order.get("customerName") == "Check Shopper" and order["lines"][0]["quantity"] == 3
          and abs(order["lines"][0]["price"] - 5.0) < 0.01 and order.get("customerId"),
          f"the cashier keys {res['code']} and gets {order.get('customerName')}, 3 x {order['lines'][0]['price'] if st == 200 else '?'}")
    st, _ = drv._call("POST", f"/api/online-orders/{res['code']}/taken", a.token, json_body={}, raw=True)
    st, again = drv._call("GET", f"/api/online-orders/{res['code']}", a.token, raw=True)
    check(st == 404, "once rung up, the code is no longer open")
    drv._call("POST", f"/api/product-sales/{sale2['id']}/end", a.token, json_body={}, raw=True)

    if not os.environ.get("KEEP"):
        sql(f"DELETE l FROM CustomerReservationLines l JOIN CustomerReservations r ON r.Id=l.ReservationId JOIN CustomerAppAccounts a ON a.Id=r.AccountId WHERE a.Phone IN ('{phone}','{new_phone}'); "
            f"DELETE r FROM CustomerReservations r JOIN CustomerAppAccounts a ON a.Id=r.AccountId WHERE a.Phone IN ('{phone}','{new_phone}'); "
            f"DELETE FROM CustomerAppAccounts WHERE Phone IN ('{phone}','{new_phone}'); "
            f"DELETE FROM Customers WHERE Phone IN ('{phone}','{new_phone}') AND UpdatedBy='customer-app'; "
            f"DELETE FROM CustomerCampaigns WHERE Title LIKE '%CHILI POWDER%' AND CreatedBy IS NOT NULL AND CreatedAt > DATEADD(minute,-10,GETDATE());")
    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

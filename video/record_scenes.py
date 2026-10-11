"""Captures the real screens for the Rush Sale presentation video into video/frames/.

Needs PesoWeb (API :5071, screens :4200) and the customer app (:8090) running, and the data from scripts/rush_sale_demo_data.py.
A first-time shopper (Maria Reyes, 0917 555 0142) registers on the phone; her records are removed first so the run can be repeated.

    python video/record_scenes.py
"""
import asyncio
import datetime as dt
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser                                 # noqa: E402

FRAMES = Path(__file__).resolve().parent / "frames"
PESOWEB = "http://127.0.0.1:4200"
APP = "http://localhost:8090/index.html"
PHONE = "09175550142"
EARLIER = [("Ana Cruz", "09175550101"), ("Pedro Lim", "09175550102"), ("Liza Tan", "09175550103")]   # already registered before the sale
EMAIL, PASSWORD = "superuser@520minimart.test", "Abc123##"


def sql(q):
    subprocess.run(["sqlcmd", "-S", r"(localdb)\MSSQLLocalDB", "-d", "PesoWeb_MissionDev", "-E", "-b", "-Q", q], check=True, capture_output=True)


def forget_shopper():
    phones = ",".join(f"'{p}'" for p in [PHONE] + [p for _, p in EARLIER])
    sql(f"DELETE l FROM CustomerReservationLines l JOIN CustomerReservations r ON r.Id=l.ReservationId JOIN CustomerAppAccounts a ON a.Id=r.AccountId WHERE a.Phone IN ({phones}); "
        f"DELETE r FROM CustomerReservations r JOIN CustomerAppAccounts a ON a.Id=r.AccountId WHERE a.Phone IN ({phones}); "
        f"DELETE FROM CustomerAppAccounts WHERE Phone IN ({phones}); "
        f"DELETE FROM Customers WHERE Phone IN ({phones}) AND UpdatedBy='customer-app'; "
        f"DELETE FROM CustomerCampaigns WHERE CreatedAt > DATEADD(hour,-12,GETDATE()) AND Channel='App';")


def register_earlier_customers():
    import json
    import urllib.request
    for name, phone in EARLIER:
        req = urllib.request.Request("http://localhost:5071/api/customer-app/register", method="POST",
                                     data=json.dumps({"name": name, "phone": phone, "password": "shopper1"}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()


async def staff_login(b):
    await b.goto(f"{PESOWEB}/#/auth/login", 4)
    try:
        await b.wait_for("#email", 12)
    except TimeoutError:
        return                                  # the profile is still signed in
    await b.fill("#email", EMAIL)
    await b.fill("#password", PASSWORD)
    await b.click("#frm button[type=submit]")
    await asyncio.sleep(5)


async def main():
    forget_shopper()
    register_earlier_customers()
    today = dt.date.today()
    b = Browser()
    await b.start()
    try:
        # ---- 1. the AI finds the expiring stock (desktop)
        await b.viewport(1366, 900)
        await staff_login(b)
        await b.goto(f"{PESOWEB}/#/ai/hub?tab=counts", 6)
        await b.wait_text("Sell fast", 60)
        await asyncio.sleep(2)
        await b.shot(FRAMES / "01_ai_sell_fast.png")
        print("1 ok: AI Sell fast list")

        # ---- 2. one click: Rush sale, filled in from the AI suggestion
        until = (today + dt.timedelta(days=1)).isoformat()
        await b.goto(f"{PESOWEB}/#/pricing/sales?product=1367&pct=40&until={until}", 5)
        await b.wait_text("Suggested by AI", 40)
        await asyncio.sleep(1.5)
        await b.shot(FRAMES / "02_put_on_sale_prefilled.png")
        await b.click_text("Put on sale", "button")
        await b.wait_text("Sent to registered customers", 40)
        await asyncio.sleep(2)
        await b.shot(FRAMES / "03_put_on_sale_sent.png")
        print("2 ok: rush sale put on and customers told")

        # a second rush sale so the phone has more than one
        until2 = (today + dt.timedelta(days=2)).isoformat()
        await b.goto(f"{PESOWEB}/#/", 3)
        await b.goto(f"{PESOWEB}/#/pricing/sales?product=1019&pct=30&until={until2}", 5)
        await b.wait_text("Suggested by AI", 40)
        await b.click_text("Put on sale", "button")
        await asyncio.sleep(3)

        # ---- 3. what is waiting for approval (the AI's own markdown proposals)
        await b.goto(f"{PESOWEB}/#/pricing/approvals", 6)
        await asyncio.sleep(3)
        await b.shot(FRAMES / "04_approval_center.png")
        print("3 ok: Approval Center")

        # ---- 4. the shopper's phone: first visit, register
        await b.viewport(390, 844, mobile=True, scale=2)
        await b.goto(APP, 2)
        await b.js("localStorage.clear(); sessionStorage.clear();")
        await b.goto(APP, 3)
        await b.wait_for("#loginForm", 30)
        await b.shot(FRAMES / "05_phone_login.png")
        await b.click_text("New customer", "button")
        await b.wait_for("#regForm", 10)
        await b.fill("#regForm [name=name]", "Maria Reyes")
        await b.fill("#regForm [name=phone]", "0917 555 0142")
        await b.fill("#regForm [name=pw]", "maria123")
        await asyncio.sleep(0.5)
        await b.shot(FRAMES / "06_phone_register.png")
        await b.click("#regForm button[type=submit]")
        await b.wait_text("You are now a registered customer", 30)
        await asyncio.sleep(1.5)
        await b.shot(FRAMES / "07_phone_welcome_sale.png")
        print("4 ok: registered, sale list with the store's message")

        # ---- 5. install it like an app
        await b.click_text("Account", "button")
        await asyncio.sleep(1)
        await b.shot(FRAMES / "08_phone_install.png")

        # ---- 6. reserve from the sale list
        await b.click_text("Sale", "button")
        await asyncio.sleep(1)
        await b.js("""(function(){var btns=[].slice.call(document.querySelectorAll('[data-inc]'));
            btns.slice(0,3).forEach(function(x){x.click();});})()""")
        await asyncio.sleep(0.5)
        await b.shot(FRAMES / "09_phone_sale_added.png")
        await b.click_text("Basket", "button")
        await asyncio.sleep(1)
        await b.shot(FRAMES / "10_phone_basket.png")
        await b.click("#reserve")
        await b.wait_for(".big", 20)
        await asyncio.sleep(1)
        code = await b.js("document.querySelector('.big').innerText")
        await b.shot(FRAMES / "11_phone_reference.png")
        print("5 ok: reserved, reference", code)

        # ---- 7. the cashier keys it in (desktop POS)
        await b.viewport(1366, 900)
        await b.goto(f"{PESOWEB}/#/sales/pos", 6)
        await b.wait_text("Online order", 60)
        await asyncio.sleep(2)
        await b.click_text("Online order", "a")
        await asyncio.sleep(1)
        await b.fill(".modal.show input.form-control", code)
        await b.click_text("Find order", "button")
        await b.wait_text("Maria Reyes", 30)
        await asyncio.sleep(1)
        await b.shot(FRAMES / "12_pos_online_order.png")
        await b.click_text("Load into this sale", "button")
        await asyncio.sleep(3)
        await b.shot(FRAMES / "13_pos_loaded.png")
        print("6 ok: cashier lookup and sale loaded")
    finally:
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())

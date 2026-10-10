# 520 Minimart customer app (prototype)

A very small web app a customer can put on a phone. It is a separate folder and does not touch PesoWeb. Plain HTML, CSS and JavaScript: no build step.

## What it does

| Screen | What the customer sees |
|---|---|
| Log in | User ID **or** phone number, plus password. No email needed. |
| Sale | Clearance (super discount) first, then sale items, with the old price crossed out and days left. |
| Shop | Every product with its price, and a search box. |
| Basket | Add items, then **Reserve and pay at the store**. The app shows a code (like R4821) and a QR code for the cashier. |
| My balance | What the customer still owes, each item's deadline, overdue in red. |
| Account | Name, user ID and email (read only). Phone number and password can be changed. |

## Try it on this PC

1. Double-click `SERVE.cmd` (needs Python).
2. Open http://localhost:8090
3. Log in: user ID `juan` (or phone `09171234567`), password `demo123`. Second customer: `maria`, same password, no balance.

## Put it on a phone

- **Same Wi-Fi:** run `SERVE.cmd`, open `http://<this PC IPv4 address>:8090` in the phone browser, then browser menu, **Add to Home screen**.
- **Real install (works like an app, offline):** host the folder on any HTTPS site (GitHub Pages, Netlify, the store's server). Android Chrome then offers **Install app**; on iPhone use Safari, Share, **Add to Home Screen**.

## The one-minute demo (customer app, then the cashier)

PesoWeb must be running with the demo feed on for company 520 Minimart (`CustomerApp__TenantId=6`, set in `appsettings.Development.json`).

1. **Phone:** open the app, log in as `juan` / `demo123`. It opens on **Sale**, clearance items first. The line under the banner says "Prices from the store system", which means the prices were downloaded from PesoWeb.
2. Press **Reserve it** on the demo basket (4 clearance and sale items). The app shows reference **R4821** and a QR code.
3. **Cashier:** in PesoWeb open **POS**, press the phone icon (**Online order**), key in `R4821`, press **Find order**. It shows **Juan Dela Cruz** and the 4 items at the clearance prices (total 377.40).
4. Press **Load into this sale**. The customer and the items are in the sale like any other, and the cashier takes payment as usual.

Any other reference gives "No online order with that reference". Prices are never typed in the app: they are live PesoWeb prices, with the fixed demo markdowns on 11 products (30% and over show as clearance).

## What is demo and what is real

- **Real:** the product list and prices are downloaded from PesoWeb (`/api/customer-app/offers`). Any approved AI markdown shows as an offer. The cashier lookup is a real PesoWeb screen and API.
- **Demo:** the 11 sale and clearance offers are fixed demo markdowns on live prices, the customer (Juan) and his reservation R4821 are fixed, and the customers and balances in `data.json` are fake.
- Reservations are saved on the phone only; PesoWeb knows only the fixed demo reference R4821.
- With no connection to PesoWeb the app shows the saved prices from `data.json`.
- Passwords in `data.json` are plain demo values. The real app must never ship passwords in a file.
- Text-message alerts (SMS) and pay online are not in this prototype. They need the server side.

## What the real version needs from PesoWeb (not built)

1. **Login:** customer account with phone or user ID and a hashed password.
2. **Catalog:** today's prices and active markdowns, including the clearance items the AI proposes and a manager approves.
3. **Reservations:** a reservation endpoint, so the code appears on the POS and the cashier scans the QR code.
4. **Balance:** the customer's open invoices and due dates.
5. **Alerts:** SMS and push when a sale or clearance starts.

The data shapes in `data.json` are what these endpoints would return, so the app screens stay the same.

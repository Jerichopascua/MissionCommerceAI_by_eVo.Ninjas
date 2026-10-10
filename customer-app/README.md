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

- **Same Wi-Fi:** run `SERVE.cmd`, open `http://<this PC's IPv4 address>:8090` in the phone browser, then browser menu, **Add to Home screen**.
- **Real install (works like an app, offline):** host the folder on any HTTPS site (GitHub Pages, Netlify, the store's server). Android Chrome then offers **Install app**; on iPhone use Safari, Share, **Add to Home Screen**.

## What is demo and what is real

- The product list, prices, offers and customers come from `data.json`, built by `make_demo_data.py` from real 520 Minimart product names. **It is demo data.**
- Reservations are saved on the phone only. The cashier does not receive them yet.
- Passwords in `data.json` are plain demo values. The real app must never ship passwords in a file.
- Text-message alerts (SMS) and pay online are not in this prototype. They need the server side.

## What the real version needs from PesoWeb (not built)

1. **Login:** customer account with phone or user ID and a hashed password.
2. **Catalog:** today's prices and active markdowns, including the clearance items the AI proposes and a manager approves.
3. **Reservations:** a reservation endpoint, so the code appears on the POS and the cashier scans the QR code.
4. **Balance:** the customer's open invoices and due dates.
5. **Alerts:** SMS and push when a sale or clearance starts.

The data shapes in `data.json` are what these endpoints would return, so the app screens stay the same.

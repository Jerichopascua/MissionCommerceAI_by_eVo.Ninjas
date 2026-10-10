# Trying the Intelligent Hub on a real company (no simulator)

Everything here uses a real company's own data in PesoWeb. The simulator is not involved: no `world.json`, no `model.json`, no pretend shoppers. The AI reads the company's real sales, stock, prices and cash through PesoWeb, and everything it proposes still goes through PesoWeb's rules and your approval.

## 0. Read this first

- **Approving is real.** If you approve a price change in the Approval Center, the real product's price changes. A reorder suggestion only becomes a *draft* purchase order; nothing is sent to a supplier.
- **Save a snapshot first**, so you can go back: sign in as `superadmin@email.com`, Intelligent Hub, **Test snapshots**, save as `before-real-test`. It is saved on drive D.
- **The AI never changes a price by itself** unless the company's own auto-approve limits allow it. List-price changes always wait for a person.

## 1. The real company you have

| | |
|---|---|
| Company | 520 Minimart (company 6 in `PesoWeb_MissionDev`), login `almaposuser1@gmail.com` |
| Products | 489, with cost and price set, stock on 489 |
| Branches | 2 |
| Real sales | 50 completed receipts on 14 trading days, **April 28 to May 30, 2026** (most between 10 PM and 1 AM) |
| Not there yet | No cash shifts, one product with an expiry date, almost no purchases |

Because the last real sales are from May, the AI is told to look at that period with `--as-of 2026-05-30`. If you make new sales in the POS today, leave `--as-of` out and it looks at the last 28 days.

## 2. Start it

1. Start PesoWeb and the screens: `powershell -ExecutionPolicy Bypass -File ui\demo\start-demo.ps1` from the project folder.
2. Open `http://127.0.0.1:4200` and sign in as the company owner (`almaposuser1@gmail.com`). Do not use the simulated logins.
3. In a second PowerShell window, start the agent for **this real company**. It asks for the password (typed on screen but not shown, never saved or printed):

```powershell
cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas\sim
python -m simpeso.agent_service --real --email almaposuser1@gmail.com --as-of 2026-05-30 --interval 20
```

Leave it running; it answers the **Run now** buttons. (To use an environment variable instead, set `PESOWEB_AGENT_PASSWORD` in that window.)

## 3. What to do in the Hub, and what to expect

Open **Intelligent Hub** in the left menu.

| Where | What to do | What you should see with this data |
|---|---|---|
| **Overview** | Choose the period **30d** or set the date range as this month; look at the two branches | Sales, margin and stock turnover from the real receipts. Today shows zero (no sales today). Days of stock is high (a 489-product shelf, thin sales) |
| **AI Control** | Press **Run now** on AI Pricing, AI Replenish, AI Customer Mission and AI Monitoring | Each card shows "Done" with a one-line summary within about 20 seconds |
| **Approval Center** (menu) | Open the AI price proposals | Each with its reason, margin before and after, a cautious profit estimate, and the rule checks. The price slope says **assumed**, because a real company's price sensitivity is not learned yet. **Reject or approve at your own judgement; approving changes the real price** |
| **Reorders** | Look at the suggestions, tick one or two, press **Create draft purchase order** | Items whose stock will not last until a delivery, with the reasoning. A Pending draft purchase appears in Purchases; stock does not change |
| **Customer missions** | Open it after Run now | A picture per branch from the 50 receipts: with most sales late at night, expect "Late night" to be the biggest mission. The page says it is an inference |
| **My tasks** | Open it | Proposals to decide, alerts, reorders for your role |
| **Alert rules** | Look at the nine rules; change a limit or assign yourself | Most stay clear with this data (no cash shifts, one expiry item) |
| **AI Impact** | Open it after you have approved a price change and waited | It will say "Too early" until there are 3 full days after the first applied AI change. That is correct |
| **AI Settings** | Switch the AI markdowns off for one branch | A branch with it off shows **Control**; the other shows **AI** |

## 4. What the real data cannot show you yet

- **Thin history.** 14 trading days of sales is enough to see the screens work, not to trust a price suggestion. The Pricing proposals will be mostly "assumed" sensitivity.
- **No effect measurement yet.** AI Impact needs real days after a real change.
- **Alerts quiet.** No cash shifts and almost no expiry stock means few alerts. Open a cash shift and close it with a difference in the POS to see a real cash alert.

## 5. To make it a stronger real test

1. Run the POS on a few real days with the AI on at one branch and off at the other; compare in **AI Impact** after about a week.
2. Receive a real delivery with expiry dates, so the markdown and expiry features have something to work on.
3. Close a cash shift each day.

## 6. If something goes wrong

- The agent says the password is wrong or the login failed: check the email, then try again.
- A card says "Failed": the one-line reason is on the card.
- To undo everything from this test: restore `before-real-test` in **Test snapshots** (or the earlier `INITIAL` snapshot).

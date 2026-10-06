# Intelligence Hub: what we learned from DMall's Data Intelligence Hub, and what we built

Written for: the Evo.Ninjas team. Source studied: the saved page `en.dmall.com/detail/23841.html` ("Data Intelligence Hub") and the pages it links to, from the mirror in `DWALL/`. The mirror kept the page text and images but not the site's style sheets or scripts, so I could not render the live layout; the visual analysis below comes from the page structure and its illustrations.

## 1. What DMall's page says the product is

DMall presents the hub as the **operations data layer of a digital store**: the screen where retail work is done online, measured as it happens, and corrected when something goes wrong. The page argues in four steps.

1. **Four problems retailers have today:** no real-time view of how the business is doing; data not used for decisions; no way to compare stores, departments and regions; problems at store level found late.
2. **One answer, five capabilities:**
   - all business workflows digitised, so management and data access happen in real time;
   - role-based operations (store manager, fulfilment, procurement, customer service) with shared data, tools and notifications, and standard workflows that speed up onboarding;
   - real-time visibility of orders, receipts, sales and inventory, with key metrics such as stock turnover and shrinkage refreshed every minute;
   - performance reports on demand by day, week, month, store, region and category, including target achievement;
   - instant notifications for anomalies, using rules the customer defines (negative margin and near-expiry products are the examples), with tasks sent automatically to the responsible person.
3. **A decision layer:** scenario-based analysis for more precise decisions.
4. **Proof and a call to action:** three customer stories, then a "partner with us" band by retail format (large supermarkets, branded convenience stores, multi-format retail).

The page shows no screenshots of the product itself, only illustrations. So the design lesson is the narrative and the information architecture, not a UI to copy.

## 2. The visual language (from the page structure and illustrations)

- Pastel blue and white surfaces, one strong blue as the accent, green for "done" checks.
- Flat "UI card" illustrations: a window frame with list rows, line and bar charts, dotted connector lines, speech-bubble labels, round icon badges.
- A soft gradient hero band with a large plain-language headline and two buttons.
- Short section headings that state the benefit ("Real-time data powering smarter decisions").
- Four problem cards in a row, each with an icon, a one-word label and one sentence.
- A two-column capability section: the capabilities as an accordion on the left (one open at a time), one illustration on the right that changes with the open item.
- Cards with generous rounding and lots of white space; stories as three image cards.

## 3. How their five capabilities map to what we have (updated 2026-10-06, all planned features built)

| DMall capability | What we have now | What is still missing |
|---|---|---|
| Digitised workflows | PesoWeb POS and back office; the Approval Center is a full workflow (propose, check, decide, log, undo); reorders become draft purchase orders; alerts are acknowledged | Stock counts and write-offs have no workflow of this kind |
| Role-based operations | Roles and permissions; **My tasks** lists what waits for the roles you hold and anything assigned to you by name | No onboarding flow |
| Real-time visibility | **Overview**: sales, margin, stock turnover, days of stock, shrinkage, expiry, exceptions, by branch and region, against sales and waste targets; refreshes every minute | Stock turnover uses the stock value now, not an average over the period; regions are free text |
| Reports on demand | **Period**, **category** and **region** pickers on the Overview | No export; no custom date range |
| Anomaly rules and notifications | **Rules**: eight rules with a limit (plus one fed by AI Monitoring), role, named assignee, severity, email and a **webhook channel**; PesoWeb checks them itself every few minutes; **My tasks**, the tab count and **browser desktop alerts** | No SMS or mobile push (needs a paid gateway); email needs the company's mail server |
| Data-driven decisions | AI price proposals with evidence **and rival prices** in the Approval Center; **AI Replenish**; **AI Customer Mission** | The mission classifier is simple (59% agreement on simulated shoppers); PesoWeb does not send the purchase order to the supplier |
| Compare stores and regions | **By region** and **Compare your branches** tables; the head company sees every company's AI settings | Region targets are the sum of the branch targets, not set separately |

## 4. What is in PesoWeb now (at `/ai/hub`)

- **Overview:** period, category and region pickers, a "refresh every minute" switch, eight headline tiles, a by-region table, the branch comparison (with sales target and waste target), and the "needs attention" list.
- **My tasks:** AI price proposals, alerts and reorders for the roles the signed-in person holds, plus anything assigned to them by name. Urgent first.
- **Reorders:** AI Replenish's suggestions with reasoning; tick some and create **draft purchase orders** (status Pending, accounting entry made, stock unchanged).
- **Customer missions:** what shoppers were trying to get done, per branch, with what it means for stock and staffing.
- **Rules:** limit, responsible role, severity, named person and email per rule, plus the **notification channel** (webhook with a test message) and browser desktop alerts.
- **AI Settings:** this company's six features, each branch's AI markdown switch, start hour, region and targets, and (head company only) every company's AI settings.
- **Approval Center:** each price proposal now shows what rivals charge. The price advisor never suggests a raise more than 5% above the lowest rival.

How the numbers are defined (kept in one place in the code, `HubMath`):

- **Stock turnover** = cost of goods sold in the period divided by the stock value on the shelf now.
- **Days of stock** = stock value divided by the period's daily cost of sales.
- **Shrinkage** = expired stock written off, plus stock lost to adjustments and stock counts (stock found offsets stock lost, never below zero), shown as a share of cost of sales.
- **Sales vs target** = sales so far divided by the daily target times the days elapsed in the period.

How AI Replenish decides (`ai/missionai/replenish.py`): reorder point = daily sales x delivery days + a safety allowance (about 90 percent service level); order up to daily sales x (delivery days + cover days) + the allowance; round up to a pack; cap perishables at what sells before they expire. Defaults: 2 delivery days, 7 cover days, 5 days of shelf life for perishables.

How AI Customer Mission decides (`ai/missionai/missions.py`): one mission per basket, the first rule that matches (weekly restock, late night, morning grab-and-go, dinner run, after-work top-up, quick top-up, everyday shop), from the hour, items, units, value and whether it held fresh food.

How the channel works: a company sets a public https address. PesoWeb posts a JSON message (with a readable `text` field) when an alert opens and, if switched on, when a price changes. Price changes use the business-event table as an outbox with a cursor, so each is sent once and a failed send is retried. The address is checked hard (https only, no private-network address, no credentials in it, and the name is resolved at send time).

## 5. Honest limits

- **Rival prices in the demo are simulated** (three made-up rivals around our price). A real company enters, imports or feeds them. There is no web scraping.
- **AI Customer Mission is a hint, not a fact.** On simulated shoppers it agreed with their real mission on 59% of baskets. A simulated world's sales carry the real clock, so for simulated worlds the baskets come from the simulator's own visit records; on a real shop it reads PesoWeb's sales.
- **Alerts** are checked by PesoWeb every few minutes for companies that have used the hub (saved rules, alerts, branch settings or a channel). A company that never opened the hub is checked the first time it does.
- **Notifications:** email only if the company has set up its mail server; the webhook is generic (it is not a connector for any particular shelf-label or e-commerce product); desktop alerts work while the page is open; SMS and mobile push are not built.
- **A task belongs to a role, or to one named person** (set on the rule), not to a team.
- **Draft purchase orders:** the supplier is the one the product was last bought from at that branch, else the company's first supplier. PesoWeb does not send the order to the supplier; a person does.
- **Replenish demo is staged** (the fastest sellers at one branch set to about a day of stock), and its evidence on simulated worlds is labelled "limited" (two baseline days).
- Branch settings cover AI markdowns, region and targets. A branch cannot yet have its own margin floors.

## 5a. AI Monitoring (added 2026-10-06)

AI Monitoring now has a **Run now** and a second job beyond the fixed rules: it compares each branch with its own recent past (`ai/missionai/monitor.py`, plain statistics, no model).

- **Sales:** the latest completed day against the middle of the previous days (at least 7 of history); flagged at half or less, or double or more, and several spreads away. Today is never judged, it is not finished.
- **Cash:** one shift closed far above the branch's usual difference (at least 100 pesos and 3 times usual); a cashier short on 3 of the last 10 shifts. Worded as "worth a look together", not an accusation.
- **Returns and deletions:** their share of the day's sales at least 10% and more than twice the branch's usual.
- **Stock ledger:** products whose shelf quantity differs from the ledger.

Findings are posted to `POST /api/ai/monitor-findings` and follow the rule "Unusual activity found by AI" (Owner, Watch by default; role, severity, named person and email are editable; switching the rule off closes them). Each scan is complete: a repeat updates its alert, a finding that no longer applies closes. Limits: needs history (a new shop says nothing about sales at first); thresholds are fixed, not learned; it reads PesoWeb's sales dates, which in a simulated world all carry today's clock, so the sales check is proven by tests and not by the simulated worlds.

## 6. What is not built

SMS and mobile push, a connector for a specific shelf-label or e-commerce product (the webhook is the integration point), per-branch margin floors, and an export of the Overview.

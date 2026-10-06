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

## 3. How their five capabilities map to what we have (updated 2026-10-06)

| DMall capability | What we have now | What is still missing |
|---|---|---|
| Digitised workflows | PesoWeb POS and back office; the Approval Center is a full workflow (propose, check, decide, log, undo); reorders and alerts have decide or acknowledge steps | Stock counts and write-offs have no workflow of this kind |
| Role-based operations | Roles and permissions; **My tasks** lists, for the signed-in person, what waits for the roles they hold (store manager, pricing manager, owner) | No named assignee: a task belongs to a role, not to one person; no onboarding flow |
| Real-time visibility | **Overview**: sales, gross margin, stock turnover, days of stock, shrinkage, expiry at risk, exceptions, by branch; refreshes itself every minute | No regions; stock turnover uses the stock value now, not an average over the period |
| Reports on demand | **Period** (today, yesterday, 7 days, 30 days, this month) and **category** pickers on the Overview | No export; no custom date range; no targets to compare against |
| Anomaly rules and notifications | **Rules** tab: eight rules with a limit, a responsible role, a severity and an email switch; alerts open and close by themselves; **My tasks** shows them; the count appears on the tab | Rules are checked when the hub is opened and each time the agent runner checks in, not by a service of PesoWeb's own; email needs the company's mail server; no push or SMS |
| Data-driven decisions | AI price proposals with evidence in the Approval Center; **AI Replenish** suggests what to reorder, how much, and by when | Customer Mission is not built; PesoWeb does not place the purchase order |
| Compare stores | **Compare your branches** table; the head company sees every company's AI settings | No regions |

## 4. What is in PesoWeb now (at `/ai/hub`)

- **Overview:** period and category pickers, a "refresh every minute" switch, eight headline tiles, the branch comparison table (each branch flagged OK or Check), and the "needs attention" list.
- **My tasks:** AI price proposals to decide, alerts from the rules, and reorders to place, for the roles the signed-in person holds. Urgent first. Alerts can be acknowledged; reorders marked Ordered or Dismissed.
- **Reorders:** the suggestions from AI Replenish with the reasoning, and a button to run it now.
- **Rules:** edit each rule's limit, responsible role, severity and email switch.
- **AI Settings:** this company's six features, each branch's AI markdown switch and start hour, and (head company only) every company's AI settings.

How the numbers are defined (kept in one place in the code, `HubMath`):

- **Stock turnover** = cost of goods sold in the period divided by the stock value on the shelf now.
- **Days of stock** = stock value divided by the period's daily cost of sales.
- **Shrinkage** = expired stock written off, plus stock lost to adjustments and stock counts (stock found offsets stock lost, never below zero), shown as a share of cost of sales.

How AI Replenish decides (`ai/missionai/replenish.py`): reorder point = daily sales x delivery days + a safety allowance (about 90 percent service level) for normal swings; order up to daily sales x (delivery days + cover days) + the allowance; round up to a pack; cap perishables at what sells before they expire. Defaults: 2 delivery days, 7 cover days, 5 days of shelf life for perishables. These are assumptions to set per company, not facts about suppliers.

## 5. Honest limits

- Alerts and tasks are only as fresh as the last check. There is no background service in PesoWeb for it yet; the agent runner and anyone opening the hub trigger the check.
- A task belongs to a role, not to a named person.
- AI Replenish on the simulated worlds uses the sales rate saved by the history phase (two baseline days), so its suggestions are labelled "limited". With dated sales in a live shop it uses the last 14 days and calls the evidence "learned" from 7 days.
- The reorder scenario in the demo is staged: the fastest sellers at one branch were set down to about a day of stock. Without that, the simulated shelves are stocked so deeply that nothing needs reordering.
- Branch settings cover AI markdowns only. A branch cannot yet have its own margin floors.
- Not built: AI Customer Mission, regions, a competitor price feed, push or SMS notifications.

## 6. Suggested next steps

1. A background check inside PesoWeb so alerts open without anyone opening the hub or the agent running.
2. Name an assignee on a rule or task (a person, not only a role).
3. Regions, and per-branch targets to compare against.
4. Turn a Replenish suggestion into a draft purchase order in PesoWeb.
5. AI Customer Mission.

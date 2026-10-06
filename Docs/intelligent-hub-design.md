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

## 3. How their five capabilities map to what we have

| DMall capability | What we have today | Gap | Next step |
|---|---|---|---|
| Digitised workflows | PesoWeb POS and back office; the Approval Center is a real workflow (propose, check, decide, log, undo) | Only pricing has a workflow like this | Reuse the Approval Center pattern for stock counts and write-offs |
| Role-based operations | Roles and permissions; approval lanes by role (store manager, pricing manager, owner) | No task inbox per role; no onboarding flow | A "My tasks" tab that lists what is waiting for the signed-in role |
| Real-time visibility | **Hub Overview**: today's sales, transactions, open exceptions, expiry at risk, active markdowns and waiting AI proposals, by branch | No stock turnover or shrinkage figure; the page refreshes only when you press Refresh | Add turnover and shrinkage tiles; refresh every minute |
| Reports on demand | PesoWeb's own Reports screens; the AI dashboard for AI results | The hub shows today only: no day, week, month, region or category picker | A period and category picker on the Overview |
| Anomaly rules and notifications | **Needs attention** list with fixed rules on today's numbers (open exceptions, expired stock not written off, cash difference, stock close to expiry, AI proposals waiting) | Rules are fixed in code; no editor; no notification; no automatic task for a person | A rule editor, then push notifications and task assignment |
| Data-driven decisions | AI proposals with evidence, rule checks, a conservative profit estimate and a price test, in the Approval Center | Pricing only; no Replenish or Customer Mission | Build AI Replenish next, then Customer Mission |
| Compare stores and regions | **Compare your branches** table; head-company view of every company | No regions | Add a region field to branches |

## 4. What we built from this (in PesoWeb, at `/ai/hub`)

- **Overview tab:** a hero band, six headline tiles, a branch comparison table with sales bars and an OK or Check flag per branch, and the "needs attention" list with links to where each item is handled.
- **AI Settings tab (the three levels you asked for):**
  - this company: the six AI features with a switch each (enforced by PesoWeb);
  - each branch: whether the AI may mark down there, and the hour before which it may not (enforced by PesoWeb on AI markdowns; a person can still mark down by hand);
  - the head company: a read-only table of every company's AI features, pricing autonomy, margin floors, auto-approve, waiting approvals and branch count, with a filter.
- **A one-page explainer** in DMall's narrative style at `ui/hub/index.html`: the four problems, the five capabilities with screenshots of the real screens, the results, and the honest limits.

## 5. Honest limits of what is built

- The Overview shows today's numbers, refreshed on demand. It is not yet "every minute", and it has no stock turnover or shrinkage tile.
- The "needs attention" rules are fixed. Nothing is notified and no task is assigned yet.
- Branch settings cover AI markdowns only (on or off, and a start hour). A branch cannot yet have its own margin floors or its own AI Loss Prevention budget.
- AI Replenish and AI Customer Mission are not built, and the hub says so.

## 6. Suggested order for the next steps

1. Auto-refresh and the turnover and shrinkage tiles (small).
2. A period and category picker on the Overview (medium).
3. "My tasks" for the signed-in role, fed by the Approval Center and the anomaly rules (medium).
4. A rule editor and notifications (larger).
5. AI Replenish, so the hub has a second decision workflow (larger).

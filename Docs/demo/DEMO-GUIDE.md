# PesoWeb + MissionCommerce AI: screen-by-screen demo

Written for: the Evo.Ninjas team and anyone who will watch or present the demo. All screenshots were taken from the running system on 2026-10-06 (PesoWeb on localhost, the AI dashboard on localhost), by a script (`ui/demo/capture.mjs`), so they can be retaken at any time.

**What is real and what is simulated.** The companies, branches and staff (Evo Quick Mart and so on) are simulated. The 493 products, their costs and their prices are the real Alma Store shelf data. The shoppers are simulated and their reaction to price is the simulator's own assumption. The AI never sees that assumption.

---

## Part A. PesoWeb: set up in this order

PesoWeb is the retail system (POS and back office). The AI is not inside it: PesoWeb enforces the rules, and the AI is a separate program that proposes changes through PesoWeb's API. Set things up from the top down, because each level depends on the one above it.

| Order | What | Where in PesoWeb | Screen |
|---|---|---|---|
| 1 | Head company settings | Setting, then App Setting | 02 |
| 2 | Sub companies (tenants) | Subscription, then Tenants | 03 |
| 3 | Branches of each company | Setting, then Branches | 06 |
| 4 | Roles and users | Setting, then Roles; People, then Users | 04, 07 |
| 5 | Products with cost and price | Inventory, then Products | 09 |
| 6 | Margin rules and approval settings | Approval Center, then Settings | 13 |
| 7 | AI on and off | AI Control | 10 |
| 8 | Day to day: approving the AI's proposals | Approval Center | 11, 12 |

### 0. Sign in

![Login](screens/01-login.png)

Every user signs in with an email and password. A company owner sees only their own company. The head company's administrator also sees the list of all companies.

### 1. Head company settings

![Head company settings](screens/02-head-company-settings.png)

The head company is the account that runs the platform (here "PesoProfit1", tenant 1). Its General settings hold the company name, tax number, contact details and logo, plus the default accounts for sales, purchases and payroll. The other tabs (System, E-Mail, POS, Theme) hold the rest. Fill this in first, because every sub company starts from these defaults.

### 2. Sub companies (tenants)

![Tenants](screens/03-tenants-sub-companies.png)

Each customer company is a **tenant**: its own products, branches, users, prices and AI settings, kept apart from every other tenant. This list is shown to the head company only. In the simulation there are five companies in the AI world (tenants 221 to 225: Quick Mart, Fresh and Pharma, Moto Parts, General Trading, Sports Hub) and five identical companies without the AI (tenants 226 to 230), so the two can be compared fairly. The login page also has a "Create new account" link for a company to register itself (not shown in the simulation, where the companies were created by script).

### 3. Branches

![Branches](screens/06-company-branches.png)

Switch to a company owner (here Evo Quick Mart). A branch is a store or warehouse. Each company has at least one; this one has two ("Main Warehouse" and "Mandaluyong 2"). Stock, sales, cash shifts and expiry are tracked per branch, while the **list price** of a product is company-wide. That distinction matters for the AI: a list-price change touches every branch, so it always needs a person.

![Company dashboard](screens/05-company-dashboard.png)

The owner's dashboard shows the day's sales, expenses, profit and low stock for the active branch.

### 4. Roles and users

![Roles](screens/04-roles.png)

![Users](screens/07-company-users.png)

Roles decide who can do what. The owner role (SuperAdmin) has every permission. The AI features added four permissions: `AI.Control` (switch AI features on and off) and `Pricing.Approve.Store`, `Pricing.Approve.Pricing` and `Pricing.Approve.Owner` (who may approve which size of AI price change). Users are the owner and the branch staff.

### 5. Products with cost and price

![Products](screens/09-products-with-cost.png)

The AI can only reason about profit if it knows what each product **costs**. This screen shows cost, sale price, stock and expiry monitoring for every product (493 here). Products that go off quickly have "Monitor Expiry" on, which is what lets the AI clear stock before it expires.

### 6. Margin rules and approval settings

![Approval settings](screens/13-approval-center-settings.png)

The owner sets the guardrails the AI cannot override:

- **Pricing autonomy:** Autonomous, Approval (every change waits for a person) or Off.
- **Margin floors:** the hard floor (never below cost plus a percentage, cannot be waived) and the soft floor (below it, a person must approve), plus the deepest markdown allowed and the most price changes per product per hour.
- **Lane sizes:** which size of change goes to the store manager, the pricing manager or the owner.
- **Largest single price increase** and **how long a proposal waits** before it expires.
- **Auto-approve small, learned changes:** off by default.

### 7. Switching the AI on and off

![AI Control](screens/10-ai-control.png)

AI Control lists the six AI features, whether each is built, and a switch for each. Switching AI Pricing off takes effect at once: PesoWeb refuses what that AI proposes, even if the agent keeps running. **Run now** asks the agent to run (the agent is a separate program, and the card shows the result of the last run). Only AI Pricing can run today. Replenish and Customer Mission are shown as "Not built yet", on purpose, so nobody thinks they work.

### 8. Approving the AI's proposals

![Approval Center queue](screens/11-approval-center-queue.png)

The Approval Center is one inbox for every price change that needs a person. Proposals are sorted into lanes by size and risk (pricing manager, owner, store manager). The counters show how many are waiting, how long the oldest has waited, the profit at stake, and how many were approved today.

![A proposal with its evidence](screens/12-approval-center-owner-lane-item.png)

Select a proposal to see why. This one is a +10% raise on a top-selling beer. The panel shows the cost, the margin before and after, the price sensitivity the AI learned from this shop's own sales, the expected profit and the conservative profit if customers are more price-sensitive, and the rule checks (one amber warning: top sellers go to the owner). The person can approve, reject, or **approve at a different price** with the slider. Everything is logged.

---

## Part B. The AI dashboard (MissionCommerce AI results)

![AI dashboard](screens/14-ai-dashboard-real-run.png)

The AI dashboard shows recorded runs of the AI against the real PesoWeb. The top card is the run on the real catalog: the AI Pricing flow (proposals into the Approval Center, a simulated approver, then the markdown agent), compared day by day with the same shop without the AI. After the two shops were made truly identical (stock and lot sizes equalised, and checked with a no-AI run that showed zero difference), the AI ended ahead on all 10 trial days: gross margin about +236 pesos a day, and the markdown agent adding about +136 pesos a day on top, mostly by cutting waste. The effect is small, and the card says so.

Below it are the earlier results: the customer story (shoppers who learn when the price drops), the three-way proof (no markdown, a fixed rule, the AI agent; waste about 59% lower than doing nothing across five seeds), what the system caught and missed, and the Quick Sim scale test.

![All reports](screens/15-ai-dashboard-reports.png)

"All reports" lists every simulated run with its sales, number of AI markdowns, open exceptions and how many of the injected incidents the AI caught.

![Day report](screens/16-ai-dashboard-day-report.png)

The day report breaks one run down by group, company and branch: sales, cash, markdowns, exceptions, what went wrong and who noticed.

---

## Suggested 6-minute demo order

1. **Login** and the head company (screens 01, 02): "this is the platform, and these are the defaults" (45 seconds).
2. **Tenants** (03): "each company is separate; here are five with the AI and five without" (45 seconds).
3. **One company** (06, 05, 09): branches, then products with cost (60 seconds).
4. **Rules and switches** (13, 10): "the owner sets the limits and can switch the AI off" (60 seconds).
5. **Approval Center** (11, 12): approve one proposal live (90 seconds).
6. **AI dashboard** (14): the real-catalog card and the three-way proof, with the honest caveats (90 seconds).

## Be ready to say plainly

- The shoppers and their price reaction are simulated; the real part is the catalog, PesoWeb and the AI's decisions through its API.
- On your thin real margins the benefit is a few percent of gross margin, not a transformation. The bigger waste reduction (about 59%) is on generated shops with normal margins.
- The AI is not tested on the AMD GPU yet. That test comes last, when everything else is ready.
- Not built yet: AI Replenish, AI Customer Mission, a competitor price feed.

## How to retake the screenshots

```
# start PesoWeb (5071), the Angular app (4200) and the dashboard (8080), then:
node ui/demo/capture.mjs <shots.json> Docs/demo/screens
```

`ui/demo/capture.mjs` drives a headless Chrome through the real login page. Logins are in `sim/runs/CREDENTIALS.txt` (not in git). The tool needs no downloads: Node 22 and the Chrome already installed.

# MissionCommerce AI inside PesoWeb: how it was built, the tech stack, and how it answers "Reinvent Commerce"

**Hackathon:** AMD Developer Hackathon, Act III. **Track 3, Reinvent Commerce:** *Help a business understand its customers and take better action.* **Team:** Evo.Ninjas.

A plainer version of this document is in `Docs/ai-in-pesoweb-simple-explainer.md`. A click-by-click tour is in `Docs/demo/DEMO-GUIDE.md`. A folder map is in `Docs/folder-structure.md`.

---

## 1. Summary

PesoWeb is a working multi-tenant retail POS and ERP (sales, purchasing, stock with expiry batches and FEFO, cash shifts, accounting). Retailers have the data but not the decisions. We added an AI layer that reads PesoWeb's data, proposes commercial actions (markdowns, list prices, reorders, alerts, customer-mission insight), and lets PesoWeb enforce rules, approvals and on/off switches before anything changes.

The design principle is that **the AI proposes and PesoWeb disposes.** Every number the AI produces comes from a statistical model that can be inspected. A language model is used only to put a finished decision into words and to generate simulated shopper profiles. It is never in the decision path and never the only forecasting method.

---

## 2. Architecture

```
 Simulator (Python)  ----plays shoppers/staff---->  PesoWeb API  <----reads (AI.Read)----  AI layer (Python)
 sim/simpeso                                         ASP.NET Core                            ai/missionai
                                                     EF Core, SQL Server                     proposes via /api/ai/*
                                                         |                                        |
                                                         |   guardrails, approval lanes,          |
                                                         |   on/off switches, audit log           |
                                                         v                                        |
                                              Angular screens: Intelligent Hub, Approval Center,  |
                                              AI Control  <------------ person approves ----------+
```

- **Back end:** ASP.NET Core (.NET 9), Entity Framework Core 7, SQL Server (LocalDB for development); JWT login; claim-based permissions; per-tenant data isolation by `TenantID`.
- **Front end:** Angular 16 (NgModule), the Intelligent Hub menu group, Approval Center, AI Control, Test snapshots.
- **AI layer:** Python with numpy. It talks to PesoWeb only through the API with a limited `AI.Read` login.
- **Agent runner:** `python -m simpeso.agent_service` polls PesoWeb for "Run now" requests and runs the six features.
- **Simulator:** a seeded Python program that drives the real PesoWeb API as shoppers, cashiers and staff.

---

## 3. The AI tech stack, and what each part is for

| Layer | Technology | Used for | Decision path? |
|---|---|---|---|
| Demand response | Poisson model: units ≈ base × (price ratio)^β, β a category log-price slope fitted by maximum likelihood with a ridge prior; hour-of-day profile | Predicting how sales change with price, and how many units will still sell before expiry | **Yes** (statistics) |
| Price advisor | Profit maximisation over a bounded price step (default 10%); margin floor; "no-regret" test at β−1; cap at 5% above the lowest rival price | Suggesting list prices | **Yes** |
| Markdown optimizer | Discount ladder 0 to 50%; value = expected revenue minus sunk cost; must beat "no markdown" by a margin | Clearing short-dated stock | **Yes** |
| AI Replenish | Reorder point = rate × lead time + z·σ·√lead (z = 1.28, about 90% service level); order up to rate × (lead + cover) + safety; pack rounding; cap perishables at shelf life | What and how much to order | **Yes** |
| AI Customer Mission | Transparent rules over a basket's hour, items, units, value and fresh-food flag | Inferring why shoppers came (quick top-up, dinner run, weekly restock...) | **Yes**, labelled an inference |
| AI Monitoring | Median and MAD of a branch's own history; thresholds for sales, cash differences, returns, ledger drift | Flagging what is out of the ordinary | **Yes** |
| Loss prevention | Ranking by value, speed and unreported deliveries | Deciding which products to count first | **Yes** |
| LLM (Qwen2.5-7B-Instruct on vLLM, AMD ROCm) | Language model | Wording explanations ("template sentence" fallback if the endpoint is down); generating simulated shopper personas | **No** |
| PyTorch on ROCm | GPU tensor computing | The aggregated "Quick Sim" lane (200,000 simulated individuals for 28 days) and persona/event generation | No (simulation only) |

**How a prediction is calculated (the track asks for this).** The demand model counts units sold per window at the prices actually charged, fits the category's price slope β, and predicts `units(p) = units_now × (p / p_now)^β`. With little data β stays near a prior and the output is labelled "assumed"; with price variation it moves toward the data and is labelled "learned". Quick Sim's price-aware forecast has 16.3% error against 26.7% for a seasonal-naive baseline. No prediction depends on a language model.

---

## 4. How the features were put into PesoWeb, in order

Each step lists what was added and the principle behind it.

1. **Data feeds for the AI.** Read-only endpoints (`/api/ai/events`, `cash-shifts`, `ledger-drift`, `expiry-risk`, `price-changes`, `movements`, `baskets`, `receipts`, `batches`) and a business-events table. A dedicated `AI.Read` permission. *The AI sees data but cannot write money.*
2. **Guarded price changes.** Markdown guardrails (hard and soft margin floors, maximum discount, maximum changes per hour, autonomy modes Off, Approval and Autonomous) and an append-only `PriceChanges` audit table. *PesoWeb is the authority; the AI's request can be refused.*
3. **Approval Center.** List-price changes always wait for a person. Three approval lanes (Store manager, Pricing manager, Owner), evidence and rule checks on each proposal, approve, reject, approve at an edited price, undo. A simulated approver stands in for a person in test runs.
4. **AI Control.** Per-company on/off for six features, enforced server-side (a switched-off feature gets `AI_FEATURE_OFF`), a "Run now" request queue, and the agent runner that serves it.
5. **Branch settings.** Per branch: AI markdowns on/off, the hour before which the AI may not mark down, region, sales target and waste target. A branch with AI markdowns off acts as a control; an **AI** or **Control** chip shows it.
6. **Intelligent Hub.** Overview by period, category and region (sales, margin, stock turnover, days of stock, shrinkage, expiry at risk, exceptions, targets); My tasks by role or named assignee; eight alert rules plus one fed by AI Monitoring, checked by a background service; email, webhook and desktop notifications.
7. **AI Replenish.** Suggestions with reasoning, turned into **Pending** draft purchase orders (same accounting entry as any purchase, no stock change until received).
8. **AI Customer Mission and competitor prices.** Mission shares per branch; rival prices from a feed or by hand, shown beside each proposal in the Approval Center and used to cap price rises.
9. **AI Monitoring.** Run-now plus a scan that compares each branch with its own recent past and posts findings that follow a rule (Owner, Watch by default).
10. **AI Impact.** Equal windows before and after the AI started pricing, and AI branches against control branches (difference in differences), with an explicit "indicative, not proof" caveat. It notes that a list price moves every branch, so the control comparison counts markdowns only.
11. **Test snapshots.** Whole-database snapshots with an initial snapshot per database structure, a safety snapshot before restore, and a refusal to restore if the structure (tables, columns, stored procedures, migrations) differs.
12. **Simulation and proof.** A seeded simulator on the real API, a real catalog of an actual store (493 products) with simulated shoppers, twin worlds equalised before each trial and verified by an A/A check.

---

## 5. How it answers "Reinvent Commerce"

| What the brief asks for | How we answer it |
|---|---|
| A real customer or merchant problem | Waste of short-dated goods, prices set by habit, stockouts, and cash and stock leakage in small retail |
| A useful commercial action | A concrete action each time: a markdown, a list price, a draft purchase order, an alert, with the reason attached |
| Relevant recommendations or personalization | Price sensitivity learned from each shop's own sales; reorders per branch from its own rate of sale; customer missions per branch |
| A measurable effect | Twin worlds, AI against no AI: AI ahead on 10 of 10 test days, about +8% gross margin, units roughly flat, waste about 160 pesos a day lower. Modest, and reported as such |
| Explain predictions; no LLM as the only forecaster | Section 3. The decision path is statistical; the LLM is wording only |
| Ideas the brief lists | Demand and inventory planning (AI Replenish), promotion planning (markdowns and list prices), customer behaviour (Customer Mission), service quality (Monitoring) |

---

## 6. Evidence and test counts

- PesoWeb back end: 277 tests. AI layer: 152. Simulator: 170.
- Live checks against a running PesoWeb: Approval Center 17, AI Control 23, Intelligent Hub 22, extras 20, background check 6, AI Monitoring 9, AI Impact 11, snapshots 18.
- Corrected showcase (`Docs/showcase-results.md`): an earlier comparison was biased because the two worlds were not identical; it was withdrawn, and the A/A check was added.

---

## 7. Honest limits

- Shoppers and their reaction to price are simulated; that reaction is the simulator's own assumption and is hidden from the AI. The catalog and prices are real.
- The gain on real thin margins is a few percent of gross margin.
- AI Customer Mission matched the simulated shoppers' true mission on about 59% of baskets.
- Competitor prices in the demo are a simulated feed. Email needs the company's mail server. The webhook is generic: no SMS and no shelf-label connector.
- AI Impact needs several days of real history; one AI branch against one control is a weak comparison.
- The AMD GPU run (PyTorch on ROCm, Qwen on vLLM) is the last step and has not been recorded. The code runs on CPU too.

---

## 8. Run it

```powershell
cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas
powershell -ExecutionPolicy Bypass -File ui\demo\start-demo.ps1        # PesoWeb, screens, dashboard
cd sim
python -m simpeso.runner day --run real2 --day 400                      # play a business day
python -m simpeso.agent_service --run real2 --company c1 --interval 30  # lets Run now work
```

Open `http://127.0.0.1:4200/#/ai/hub` and use the **Intelligent Hub** menu group.

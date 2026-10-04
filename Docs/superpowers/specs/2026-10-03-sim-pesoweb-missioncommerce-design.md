# MissionCommerce AI + Sim.PesoWeb: Design

Team Evo.Ninjas | AMD Developer Hackathon: Act III | Track 3: Reinvent Commerce
Date: 2026-10-03 (revised 2026-10-04: markdown headline, corporate group) | Build window: kickoff Oct 12 11:00 PM PHT, submissions close Oct 18 10:00 PM PHT

## 1. Thesis

> An autonomous AI prices every branch of a corporate group down to the SKU and batch, inside margin guardrails, so less revenue is wasted. Sim.PesoWeb then proves it: it runs the real system in a synthetic retail world, records what the AI *predicted*, and measures what *actually* happened against a baseline.

Supporting evidence from the same world: customer missions that feed the pricing decisions, and incidents the system missed (cash variance, shrinkage) that the AI finds.

Four pieces, one story:

| Piece | Role |
|---|---|
| PesoWeb / PesoPOS | The real commerce platform and the **system under test**. Minimal, additive changes only. |
| Sim.PesoWeb | The synthetic world that operates PesoWeb through its real APIs |
| MissionCommerce AI | Mission detection, forecasting, anomaly detection, LLM investigator and recommender |
| AMD (Developer Cloud, ROCm) | vLLM serving, PyTorch models, GPU event generation |

## 2. Decisions (settled in brainstorming)

1. **Demo spine (decided 2026-10-04): agentic markdown pricing is the headline**, monitored by branch across a corporate group, with a **predicted-vs-realized proof** from Sim.PesoWeb. Caught-vs-Missed and Mission detection are supporting: missions feed pricing, incidents show the AI protecting the business.
6. **Corporate group:** one group, several companies, each company **is one PesoWeb tenant** with many branches (warehouses). Companies can open new branches during a run, and the simulator does so.
2. **AMD workload:** Developer Cloud Instinct GPU running vLLM (ROCm) for the LLM, and PyTorch (ROCm) for forecast, mission and anomaly models and for Quick Sim generation. `rocm-smi` and throughput are visible in the demo.
3. **Architecture (Approach A):** a Python Sim service on AMD drives PesoWeb through its real HTTP APIs. Quick Sim runs on a separate **aggregated lane** that never goes through the POS API and is labelled as aggregated.
4. **PesoWeb changes:** 13 additive items (section 4). All else deferred.
5. **Forecasting must not be LLM-only** (hackathon rule). A statistical/ML model forecasts, and the LLM explains and triggers actions.

## 3. Architecture

```
                      SIM CONTROL PANEL (UI)
                              |
                      Simulation Controller (seeded clock)
       +----------------------+----------------------+
   DAY-TO-DAY              SCENARIO SIM            QUICK SIM
   real APIs               real APIs + injected    aggregated GPU lane
       |                   events                       |
       +----------+--------------------+-----------------+
                  v
   WorldEngine -> BehaviorEngine -> ScenarioEngine
   (tenants, branches, products,   (demand curves, random events,  (YAML: normal/critical/defined)
    suppliers, actors, missions)     trend signals, queue model)
                  |
          PesoWebDriver (virtual cashier/manager/inventory users, real login + APIs)
                  v
              PESOWEB  --(BusinessEvent outbox, /api/ai/*)-->  AI SERVICE (AMD)
                  |                                         +- Signal + Mission Detection
          Exception Center (basic rules)                    +- Demand Forecast (GBM / time-series)
                  |                                         +- Anomaly detectors
                  +------------------------+                +- LLM investigator + recommender (vLLM)
                                           v
                       INCIDENT LEDGER + SCORING
        (ground truth vs system-caught vs AI-found vs undetected; Week 0 vs Week 3 KPIs)
```

### Two closed loops on one world

**Mission loop (growth, feeds pricing).** Mission signals and segment mix are inputs to the markdown engine. Each synthetic customer carries a hidden mission (grab-and-go breakfast, after-work top-up, late-night emergency, and so on). Signal Engine (time x basket x branch) feeds Mission Detection, then the Demand/Action Engine (forecast plus LLM recommendation) produces assortment, stock, price and bundle actions. The actions are applied in the sim and Week 3 is run. The simulator knows true missions, so the detector is scored on precision and recall.

**Incident loop (protection).** The simulator **injects** incidents and records ground truth `{id, type, branch, injected_at}`. After the run:
1. PesoWeb Exception Center raised a matching exception: **System caught**.
2. Otherwise the AI detector flagged it: **AI discovered**.
3. Otherwise: **Undetected** (reported honestly).

Detection coverage = (caught + AI-found) / injected. Every figure comes from a run.

### Corporate group (company = tenant)

```
CORPORATE GROUP
  +- Company A (tenant)  -> Branch A1, A2, A3 ... (warehouses)
  +- Company B (tenant)  -> Branch B1, B2 ...
  +- Company C ... D ... E
```

- Each company is a normal PesoWeb tenant created through the real `Auth/Register`, so isolation, settings, currency, tax and plan tier stay per company. A thin `CorporateGroup` link ties the tenants together (section 4, item 9). No change to how existing tenants work.
- Companies have **many branches**. The Business tier caps at 5 branches, so group companies use an **Enterprise** tier row in the editable `SubscriptionTierLimits` table (a data change, not code).
- **Expansion is simulated:** a company adds branches mid-run (`AddWarehouse`, assortment copy, staff, opening stock through a purchase receipt). Scenario example: "Company C opens 3 branches in week 2." The markdown engine and monitoring must pick up new branches without restart.
- **Group Command Center:** a read-only roll-up from group to company to branch (sales, margin, waste in pesos, near-expiry money at risk, markdowns executed, guardrail blocks, exceptions). Cross-tenant reads require explicit group membership, are read-only, are filtered to the group's tenant list, and are audited. They never write.
- The simulated group owner is a "conglomerate" owner archetype that plans several companies at once, each with its own vertical mix and branch count.

### Agentic markdown pricing (PesoProfit)

Headline feature. The agent decides and executes continuously through the trading day, per branch, per SKU and per batch, and PesoWeb enforces the rules the agent cannot override.

**Signals:** expiry by batch (time left), stock on hand and rate of sale per SKU and branch, competitor prices (a simulated competitor feed supplied by the simulator; no real scraping), time of day and mission mix, customer segment mix.

**Decision:** for each at-risk batch, choose a discount from a bounded ladder (defined by the tenant's policy) that maximizes expected margin from units sold at the new price minus the write-off cost of units left at expiry. A demand-response model per branch, SKU and segment, learned from observed sales (gradient boosting or a Poisson regression with price as a feature), supplies the expected units. The LLM explains each decision and is **not** in the decision path.

**Guardrails (enforced inside PesoWeb on every markdown write):** hard margin floor (the price never goes below cost plus the floor), soft floor (below it needs approval), maximum discount, maximum price changes per SKU per hour, per-branch waste target. A tenant policy sets the autonomy mode: autonomous within guardrails, approval required, or off.

**Execution and sync:** the agent calls the PesoWeb markdown API. PesoWeb validates, writes the active markdown and a price-change ledger row, and emits a `PriceChanged` event. The POS applies the price at sale time. Simulated electronic-shelf-label, e-commerce and picker channels acknowledge the event, and the lag is measured.

**Customer behavior:** every synthetic archetype and mission has a hidden price response (elasticity) in the simulator. The AI never sees it and must estimate it from sales.

**Proof (predicted vs realized):**
1. Before executing, the agent records its prediction: units sold by expiry, margin, and waste in pesos, with an interval.
2. The simulator plays out the real outcome.
3. We report the calibration error between prediction and outcome.
4. The same seed runs three ways: no markdown, a fixed rule (for example 50% off on the last day), and the AI. We compare waste, margin, sell-through and revenue.

**Honest limit, stated on stage:** the price response is our own assumption in the simulator. The proof shows the mechanism, the guardrails and the prediction accuracy under that assumption. It is not a claim about real-market lift.

### Simulation modes

| Mode | Path | Purpose |
|---|---|---|
| Day-to-Day | Virtual clock steps one business day. Actors log in and operate real PesoWeb. A human can log into the same tenant and watch. | Real operation |
| Scenario Sim | YAML scenario (hand-written or LLM-generated) on the Day-to-Day lane with injected events, plus KPIs | What-if and stress |
| Quick Sim | Vectorised GPU generation, with forecast and anomaly models run over the result. Reports events/sec and virtual-days/sec. | Scale |

### Actors: owners first, then staff and shoppers

The world is **two-sided**. Owner agents are the SaaS customers: they sign up to PesoWeb, pick a plan, and create the tenants, branches, staff and catalogs that shopper agents then visit.

| Layer | Method |
|---|---|
| Owner archetypes (~50-100) | LLM (vLLM, JSON schema) once, cached and versioned: intent, capital band, ambition, risk, vertical affinity |
| Owner instances | Correlated-trait sampling (capital, ambition, vertical); named, located |
| Business plan | LLM per owner (batched) then validated: vertical, concept, # branches, # staff per branch, catalog size, margin policy, hours |
| Corporate owners | A conglomerate archetype plans a group of several companies (tenants), each with its own vertical mix, branch count and expansion plan; companies sit on the Enterprise tier |
| Tier choice | Rule + traits, **constrained by `SubscriptionTierLimit`** (seed: Lite 1 branch/1 user/1,000 products; Pro 2/3/5,000; Business 5/10/50,000 - confirm in P0 that this is implemented). Plan exceeding tier means downsize or upgrade, recorded as a decision. |
| Onboarding | `PesoWebDriver` via real APIs: `Auth/Register` -> `AddWarehouse` x N -> `AddUser` x staff -> categories/products (or CSV bulk import) -> opening stock via purchase receipt |
| Lifecycle | Trial -> paid -> upgrade -> churn (SaaS funnel metric) |
| Staff | Per-branch role mix with trait profile (speed, accuracy, reliability). Incidents are injected against staff as **ground truth only**; wording is always "unexplained variance", never an accusation. |
| Shoppers | Persona archetype (LLM, cached) -> correlated instances -> weekly habit plan -> needs-based decision policy -> small bounded noise. Missions fit the branch's vertical. |

**Principle:** the LLM writes who people are; models decide what they do; dice only add small noise; plausibility constraints keep it honest. The seed fixes the dice so reruns match; it does not make personas random. LLM cost is bounded because only archetypes, plans and "hero" actors (a few hundred, batch-generated) use the LLM; populations at scale are sampled from archetypes.

**No real-data calibration is assumed.** Realism is enforced by constraints (margin bands per vertical, price/cost sanity, catalog size vs capital, staff vs branch size and ticket volume, traffic bands per vertical and location type, diversity across owners). Known limit, stated on stage: the population is plausible, not proven representative.

### Verticals (templates are data, not code)

A vertical template (LLM-generated once, validated) defines catalog size range, categories, price/cost margin band, ticket size, expiry on/off, shopper missions, traffic band and relevant incidents.

| Vertical | Tier | Expiry/FEFO | Main missions |
|---|---|---|---|
| Convenience store | A (full depth) | Yes | Grab-and-go, after-work top-up, late-night |
| Grocery / pharmacy | A (full depth) | Yes | Weekly restock, urgent medicine |
| Motorcycle parts | B (end-to-end, template-driven) | No | Repair-urgent, scheduled maintenance, accessory browse |
| Mixed store | C (blend of two templates) | Partial | Combination |
| Sports | C (template only, seasonal) | No | Event-driven, hobby |

Electronics is roadmap (serial/warranty logic is not in PesoWeb). High-ticket verticals show cash variance and shrinkage at a different scale (a missing high-value item rather than a low-value perishable), supporting the "works across business types" claim.

### Customer population sizing

Customers have two layers. **Archetypes** are LLM-written personality templates (office worker after work, student on a budget, night-shift nurse, parent doing a weekly shop, motorcycle commuter, and so on). **Individuals** are named customers instantiated from an archetype, each with their own wallet, habits, home area, favourite branch and history. Individuals must persist, because repeat visits, loyalty and churn are what Mission Detection looks for.

Archetypes come from a coverage grid (age band x income band x occupation x household x mobility x time pattern) that the LLM fills cell by cell; near-duplicates are removed by text similarity. The library fails validation if the grid has empty cells or archetypes cluster too tightly.

Regular-customer pool per branch: `pool ~ daily_txns x regular_share x avg_days_between_visits`. Example: 400 txns/day x 0.65 x 3 = ~780 regulars. `regular_share` and `avg_days_between_visits` are tunable design parameters per vertical, not measured facts. Anonymous walk-ins are drawn from archetype mix on top of the pool.

The design target is the **full** profile, because real supermarkets serve thousands of distinct customers a day. The hackathon build runs the **starter** profile. Both use the same code; a `population_profile` setting changes only the numbers.

| Parameter | `starter` (hackathon build) | `full` (design target) |
|---|---|---|
| Customer archetypes | ~40 (convenience 15, grocery/pharmacy 15, motorcycle 10; mixed and sports reuse) | ~150 (about 30 each for Tier A verticals) |
| Day-to-Day world | 1 group, 5 companies, ~20 branches (4 per company, plus 2-3 expansion openings) | 1 group, 5 companies, ~50 branches (about 10 per company); size set by measured PesoWeb API throughput |
| Named individuals, Day-to-Day | ~3,000 | ~10,000 |
| Hero actors (LLM day scripts) | ~100 | ~300 |
| Supermarket branch (high traffic) | ~2,000 txns/day, ~5,000 regulars | ~10,000 txns/day, ~25,000 regulars (10,000 x 0.5 x 5) |
| Quick Sim individuals (GPU rows) | ~100,000 | ~1-2 million |
| Micro-store free tier | Archetype-mix counts only | Archetype-mix counts only (aggregated, labelled) |

The starter profile caps hackathon cost, mainly LLM generation time and API throughput. It does not cap the model: every actor type, mission and incident works at either size.

### Reproducibility

Every run takes a seed. The same seed and scenario give an identical event log (hash-checked). The Week 0 vs Week 3 comparison runs the same seed with and without AI actions.

## 4. Phase 1: PesoWeb additions (all additive; items 9-13 added 2026-10-04)

Existing: `TenantID` everywhere, `Warehouse` (branch), `Role`, `AuditLog`, `InventoryTransaction`, `ProductBatch` and FEFO service, `StockAdjustment`, `StockTransfer`, `Purchase`, `SaleReturn`, Kuya Pedro spec.

| # | Addition | Footprint | Powers |
|---|---|---|---|
| 1 | Cashier Shift and Cash Drawer | New `CashShift`, `CashMovement`. Nullable `ShiftId`, `CashierId`, `PosTerminal` on `Sale`. Endpoints: open shift, cash-in/out, close with count. `Expected = Opening + CashSales + CashIn - CashRefunds - CashOut`; `Variance = Actual - Expected`. | Cash variance |
| 2 | Sale lifecycle events | New `SaleEvent` (Voided, Refunded, Discounted, ManualAdjust), written from existing sale/return paths | Unusual refunds and voids |
| 3 | Ledger and audit hardening | `InventoryTransaction`: add `QtyBefore`, `QtyAfter`, `UserId`. `AuditLog`: add branch, reference, before/after values. | Phantom inventory |
| 4 | Stock count with variance | New `StockCount`, `StockCountLine`. Approval posts a `StockAdjustment`. | Shrinkage |
| 5 | Expiry money-at-risk | Read-only qty x cost over `ProductBatch`: "at risk" and "already wasted" | Expiry loss |
| 6 | Receiving discrepancy | Expected vs received qty on `PurchaseDetail`; received-qty difference on `StockTransfer` | Short shipment, transfer loss |
| 7 | Exception Center | New `Exception`, `Incident`. Rule-based detector service: cash variance, expired stock, negative stock, stockout. Severity and evidence list screen. | System caught |
| 8 | Business event stream and Sim API | `BusinessEvent` outbox fed by services. `/api/ai/*` read endpoints. `X-Sim-Run` header tags simulator traffic. | Everything downstream |
| 9 | Corporate group link | New `CorporateGroup`, `CorporateGroupTenant`. Group-scoped read-only roll-up endpoints (explicit membership, audited, no writes). Enterprise tier row in `SubscriptionTierLimits` (data). | Group monitoring by company and branch |
| 10 | Price change ledger | New `PriceChange`: tenant, branch, product, batch, price before and after, reason, source (AI or manual), guardrail result, link to the prediction record, time | Audit and proof |
| 11 | Markdowns applied at the POS | New `ActiveMarkdown` (branch, product, optional batch, price, start and end, source). The sale price lookup in `AddSale` honours an active markdown and re-validates guardrails at sale time. | Autonomous markdown execution |
| 12 | Pricing guardrails | New `PricingPolicy` per tenant: hard and soft margin floors, maximum discount, maximum changes per SKU per hour, waste target, autonomy mode. Enforced inside PesoWeb on every markdown write. | Margin protection |
| 13 | Channel sync events | `PriceChanged` events on the outbox. Simulated shelf-label, e-commerce and picker sinks (in Sim) acknowledge, with measured lag. | Execution and sync proof |

**Important:** the markdown API never trusts the caller: a price below the hard margin floor is rejected even when the AI proposes it. Exception Center rules are intentionally basic (low stock, expiry alert, negative stock, cash variance on close). Pattern-level cash anomalies, shrinkage and abnormal refunds are **not** detected by PesoWeb. The AI layer finds them. The "missed" column is therefore real output, not slide content.

Order of work: 1, 8, 3+4, 5, then 12, 10, 11, 13, 9, then 7, then 2 and 6.

**Deferred:** branch type/hours/timezone, auditor and purchasing roles, technical-incident taxonomy, AI assistant UI (Kuya Pedro gets wired to `/api/ai/*` in Phase 3).

## 5. Sim.PesoWeb components

| Module | Responsibility |
|---|---|
| `world` | Owner agents and their business plans, tenants, branches, staff, catalogs, suppliers, shopper personas and customer missions (from archetypes and vertical templates) |
| `owner` | Owner archetypes, business-plan generation, tier-constrained decisions, onboarding journey, SaaS lifecycle |
| `verticals` | Vertical templates and catalog generation with validators |
| `behavior` | Hidden price response (elasticity) per archetype and mission, habit plans and needs-based decision policy, hourly demand curves per vertical and location type, random events, trend signals (holidays, seasonality, weather), cashier throughput and queue model |
| `corporate` | Conglomerate owner archetype, group of companies (tenants), branch counts, expansion events, group roll-up checks |
| `pricing` | Markdown optimizer, demand-response model, prediction recorder, calibration and baseline comparison |
| `channels` | Simulated shelf-label, e-commerce and picker sinks with measured lag, and the simulated competitor price feed |
| `scenario` | YAML scenarios: demand spike, supplier delay, cash short, expiry batch, POS surge/offline, branch expansion |
| `driver` | `PesoWebDriver`: virtual users calling real PesoWeb APIs |
| `lane_scale` | Aggregated GPU generation to a columnar store, then the same models |
| `ai` | Forecast, mission detection, anomaly detectors, LLM investigator and recommender |
| `scoring` | Incident ledger, detection coverage, KPI deltas |
| `api + ui` | Mode picker, clock, live counters, Caught/Missed scorecard, `rocm-smi` panel |

## 6. Feature coverage (from the team wish-list)

**In scope: produced by the engine:** wasted/lost/damaged, near-expiry, newly expired, wasted-product revenue loss, product-loss tracking, inventory count and missed-scan accuracy, order anomaly, employee anomaly count, offline branch alert, historical sales, holidays and seasonal trends, promotions, purchase quantity, demand-driven purchase orders, smart branch transfers, price-change suggestions, AI recommendations, AI assistant (Kuya Pedro), real-time alerts.

**In scope: dashboard tiles via one `/api/ai/metrics` endpoint:** inventory turnover, best sellers, shelf availability and out-of-stock, performance tracking, employee efficiency, customer flow, waiting time, multi-dimension charts (traffic, customers, transactions).

**Deferred (roadmap slide):** online reserved orders, self-pickup, work orders, service desk and complaints, procurement quality, flexible plans, automatic expense allocation, system-update flow, new-product notifications, targeted-user marketing, separate storage/transport loss types.

## 7. Phase plan

| Phase | When | Deliverable | Exit test |
|---|---|---|---|
| P0 Setup | Now to Oct 11 | ADP membership and Dev Cloud credits; ROCm + vLLM smoke test; PesoWeb demo tenant and sim API key; repo layout | `rocm-smi` visible; small LLM answers via vLLM |
| P1 PesoWeb foundation | Oct 4 to 11 | Section 4 items in the given order | Shift closes with variance; Exception Center lists a negative-stock event |
| P2 Sim core | Oct 12 to 14 | Corporate world (group, 5 companies, branches, expansion), Behavior with hidden price response, Driver, Day-to-Day, incident injection and scoring | Seeded day runs via real APIs with ground truth recorded; a new branch opens mid-run |
| P3 Intelligence on AMD | Oct 14 to 16 | Demand-response and forecast models, **markdown optimizer with guardrails**, prediction recorder, mission signals, anomaly detector, vLLM investigator, Kuya Pedro wired | Markdowns execute through the PesoWeb API within guardrails; predictions recorded; AI finds cash variance and shrinkage PesoWeb missed |
| P4 Proof + Scale | Oct 16 to 17 | Three-way run (no markdown, fixed rule, AI), predicted-vs-realized calibration, group monitoring by branch, YAML scenarios, GPU aggregate lane | Calibration error and KPI deltas from real seeded runs |
| P5 Ship | Oct 17 to 18 (10 PM) | UI polish, hosted URL, Docker + README, demo video, deck with real numbers | Fresh-clone run works; submission checklist done |

**Cut order if behind:** (1) Tier C verticals (sports, mixed); (2) Quick Sim at multi-thousand-tenant scale, so show a smaller scale with real throughput; (3) LLM-generated scenarios; (4) queue/waiting-time model; (5) Tier B vertical depth (motorcycle runs in Quick Sim only); (6) stock count approval workflow, keeping variance recording; (7) SaaS lifecycle (upgrade/churn); (8) mission-detection depth (keep two missions); (9) Exception Center breadth beyond cash and expiry.

**Never cut:** the markdown engine with PesoWeb-enforced guardrails, the predicted-vs-realized proof with a baseline, group monitoring by company and branch, cash shift and the event outbox, visible AMD usage.

## 8. Testing

- PesoWeb additions: xUnit test per rule (e.g. the expected-cash formula) against a throwaway SQL Server DB.
- Sim: seed determinism (same seed gives same event-log hash); scenario YAML schema validation.
- Scoring: golden run. Inject 5 known incidents into a small world and assert the exact caught / AI-found / undetected split.
- Models: mission detector precision/recall against simulator ground truth; forecast MAPE on a held-out simulated week with a naive baseline.
- Pricing: a markdown proposed below the hard margin floor is rejected by PesoWeb (unit test); the POS applies an active markdown at sale time; the same seed gives the identical three-way comparison; calibration error is computed against a naive predictor.
- Group: a group member can read only its own tenants' roll-up and cannot write; a non-member gets nothing.
- E2E: one scripted Day-to-Day run, reused as the demo rehearsal.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Hackathon expects work built during the event; PesoWeb pre-exists | Confirm at Discord Q&A (Oct 13, 12 AM). Keep Phase 1 as labelled additive commits; Sim.PesoWeb lives in this public repo. |
| PesoWeb HTTP throughput caps Day-to-Day volume | Size the demo world to what the API sustains; scale claims come from the aggregated lane and are labelled aggregated |
| Circular evaluation (we detect what we generated) | Score against injected ground truth only; publish baseline rules; never claim real-world accuracy |
| Dev Cloud access or quota | P0 smoke test first; AI service uses an OpenAI-compatible vLLM endpoint so a local fallback works |
| LLM slow or flaky live | Pre-compute and cache investigator output per run; live call is a bonus |
| Sim traffic polluting real tenants | `X-Sim-Run` header, dedicated sim tenants, per-run purge script |
| Onboarding chain (Register -> AddWarehouse -> AddUser -> AddProduct) fails through the API or is blocked by tier limits | Verify the chain end to end early in P1; the driver reports tier-limit refusals as events, not crashes |
| LLM personas homogeneous or stereotyped | Diversity constraints, plausibility validators, hero actors only for a few hundred |
| Agent price bypasses margin protection | Guardrails live in PesoWeb, re-checked at write and at sale time; the agent cannot override them |
| Markdown races with a sale in progress | The POS price lookup is the single source of truth at checkout; the sale records the price actually applied |
| Cross-tenant group reads leak data | Explicit membership, read-only endpoints, tenant list filter, audit log, tests for non-members |
| Predicted-vs-realized proof is circular (simulator elasticity is our assumption) | AI never sees the hidden response; compare against baselines; state the limit on stage |
| Enterprise tier and many-branch tenants strain API throughput | Size the demo group to measured throughput; expansion adds a few branches, not hundreds |
| Pricing story resembles another vendor's pitch | Original wording, design and proof method; show the proof, not just the pitch |
| Time | Cut order above |

## 10. Repo layout (this repo is the public submission)

```
/pesoweb-additions   patches + SQL scripts + docs for Phase 1 (PesoWeb is the system under test)
/sim                 Python Sim.PesoWeb service
/ai                  models, vLLM serving config, investigator prompts
/ui                  control panel and scorecard
/scenarios           YAML scenarios
/docs                spec, architecture diagram, demo script, benchmark results
docker-compose.yml   sim + ui + ai (+ PesoWeb demo instance)
```

No API keys committed (env vars). MIT license. Demo-video and deck numbers come from real runs only.

## 11. Open items

- Confirm the "built during the event" rule with organizers (Oct 13).
- Confirm ADP membership and Dev Cloud credit status (P0).
- Decide Evolus partner track entry (needs Docker + README; optional).
- Confirm the Enterprise tier values (branch, user and product limits) for group companies.

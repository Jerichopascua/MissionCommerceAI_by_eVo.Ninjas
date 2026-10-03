# MissionCommerce AI + Sim.PesoWeb: Design

Team Evo.Ninjas | AMD Developer Hackathon: Act III | Track 3: Reinvent Commerce
Date: 2026-10-03 | Build window: kickoff Oct 12 11:00 PM PHT, submissions close Oct 18 10:00 PM PHT

## 1. Thesis

> We don't just generate mock data. We run the real system (PesoWeb) inside a synthetic retail world, then show two things measurably: what the AI **grows** (customer missions) and what the AI **protects** (incidents the system missed).

Four pieces, one story:

| Piece | Role |
|---|---|
| PesoWeb / PesoPOS | The real commerce platform and the **system under test**. Minimal, additive changes only. |
| Sim.PesoWeb | The synthetic world that operates PesoWeb through its real APIs |
| MissionCommerce AI | Mission detection, forecasting, anomaly detection, LLM investigator and recommender |
| AMD (Developer Cloud, ROCm) | vLLM serving, PyTorch models, GPU event generation |

## 2. Decisions (settled in brainstorming)

1. **Demo spine: Caught vs Missed**, plus the **Mission loop** from the original deck (Mission Detection is Feature 1; KPI is Week 0 vs Week 3: sales, waste, margin).
2. **AMD workload:** Developer Cloud Instinct GPU running vLLM (ROCm) for the LLM, and PyTorch (ROCm) for forecast, mission and anomaly models and for Quick Sim generation. `rocm-smi` and throughput are visible in the demo.
3. **Architecture (Approach A):** a Python Sim service on AMD drives PesoWeb through its real HTTP APIs. Quick Sim runs on a separate **aggregated lane** that never goes through the POS API and is labelled as aggregated.
4. **PesoWeb changes:** 8 additive items only (section 4). All else deferred.
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

**Mission loop (growth).** Each synthetic customer carries a hidden mission (grab-and-go breakfast, after-work top-up, late-night emergency, and so on). Signal Engine (time x basket x branch) feeds Mission Detection, then the Demand/Action Engine (forecast plus LLM recommendation) produces assortment, stock, price and bundle actions. The actions are applied in the sim and Week 3 is run. The simulator knows true missions, so the detector is scored on precision and recall.

**Incident loop (protection).** The simulator **injects** incidents and records ground truth `{id, type, branch, injected_at}`. After the run:
1. PesoWeb Exception Center raised a matching exception: **System caught**.
2. Otherwise the AI detector flagged it: **AI discovered**.
3. Otherwise: **Undetected** (reported honestly).

Detection coverage = (caught + AI-found) / injected. Every figure comes from a run.

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
| Day-to-Day world | ~3 tenants, ~6 branches | ~5 tenants, ~12 branches (size set by measured PesoWeb API throughput) |
| Named individuals, Day-to-Day | ~3,000 | ~10,000 |
| Hero actors (LLM day scripts) | ~100 | ~300 |
| Supermarket branch (high traffic) | ~2,000 txns/day, ~5,000 regulars | ~10,000 txns/day, ~25,000 regulars (10,000 x 0.5 x 5) |
| Quick Sim individuals (GPU rows) | ~100,000 | ~1-2 million |
| Micro-store free tier | Archetype-mix counts only | Archetype-mix counts only (aggregated, labelled) |

The starter profile caps hackathon cost, mainly LLM generation time and API throughput. It does not cap the model: every actor type, mission and incident works at either size.

### Reproducibility

Every run takes a seed. The same seed and scenario give an identical event log (hash-checked). The Week 0 vs Week 3 comparison runs the same seed with and without AI actions.

## 4. Phase 1: PesoWeb additions (all additive)

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

**Important:** Exception Center rules are intentionally basic (low stock, expiry alert, negative stock, cash variance on close). Pattern-level cash anomalies, shrinkage and abnormal refunds are **not** detected by PesoWeb. The AI layer finds them. The "missed" column is therefore real output, not slide content.

Order of work: 1, 8, 3+4, 5, 7, then 2 and 6.

**Deferred:** branch type/hours/timezone, auditor and purchasing roles, technical-incident taxonomy, AI assistant UI (Kuya Pedro gets wired to `/api/ai/*` in Phase 3).

## 5. Sim.PesoWeb components

| Module | Responsibility |
|---|---|
| `world` | Owner agents and their business plans, tenants, branches, staff, catalogs, suppliers, shopper personas and customer missions (from archetypes and vertical templates) |
| `owner` | Owner archetypes, business-plan generation, tier-constrained decisions, onboarding journey, SaaS lifecycle |
| `verticals` | Vertical templates and catalog generation with validators |
| `behavior` | Habit plans and needs-based decision policy, hourly demand curves per vertical and location type, random events, trend signals (holidays, seasonality, weather), cashier throughput and queue model |
| `scenario` | YAML scenarios: demand spike, supplier delay, cash short, expiry batch, POS surge/offline |
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
| P2 Sim core | Oct 12 to 14 | World, Behavior, Driver, Day-to-Day, incident injection and scoring | Seeded day runs via real APIs with ground truth recorded |
| P3 Intelligence on AMD | Oct 14 to 16 | Forecast, mission detection, anomaly detector, vLLM investigator, Kuya Pedro wired | Mission precision/recall reported; AI finds cash variance and shrinkage PesoWeb missed |
| P4 Scenario + Quick Sim | Oct 16 to 17 | YAML scenarios, GPU aggregate lane, Week 0 vs Week 3 | Scorecard and KPI delta from two real runs |
| P5 Ship | Oct 17 to 18 (10 PM) | UI polish, hosted URL, Docker + README, demo video, deck with real numbers | Fresh-clone run works; submission checklist done |

**Cut order if behind:** (1) Tier C verticals (sports, mixed); (2) Quick Sim at multi-thousand-tenant scale, so show a smaller scale with real throughput; (3) LLM-generated scenarios; (4) queue/waiting-time model; (5) Tier B vertical depth (motorcycle runs in Quick Sim only); (6) stock count approval workflow, keeping variance recording; (7) SaaS lifecycle (upgrade/churn).

**Never cut:** cash shift, Exception Center, mission detection with Week 0 vs Week 3 KPI, visible AMD usage.

## 8. Testing

- PesoWeb additions: xUnit test per rule (e.g. the expected-cash formula) against a throwaway SQL Server DB.
- Sim: seed determinism (same seed gives same event-log hash); scenario YAML schema validation.
- Scoring: golden run. Inject 5 known incidents into a small world and assert the exact caught / AI-found / undetected split.
- Models: mission detector precision/recall against simulator ground truth; forecast MAPE on a held-out simulated week with a naive baseline.
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

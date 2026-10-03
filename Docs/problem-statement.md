# Problem Statement: MissionCommerce AI + Sim.PesoWeb

Team Evo.Ninjas | AMD Developer Hackathon: Act III | Track 3: Reinvent Commerce

## The organizers' challenge

> Retailers have product data, transactions, inventory, reviews, support conversations, and marketing results. These sources are often disconnected, which makes it difficult to turn them into useful decisions. Build a product that helps a business attract, serve, convert, or retain customers.

## Our problem statement

**Retail businesses manage stores by product, not by what customers are trying to do, and they find out about operational leaks only after money is gone. Neither can be tested safely at scale before it reaches real stores.**

This breaks into three problems for one user.

### Who it is for

| User | Their situation |
|---|---|
| **Retail owner or manager** (convenience, grocery, pharmacy, parts shops, multi-branch chains in the Philippines and similar markets) | Runs one to many branches on a POS/ERP. Has sales, stock, cash and supplier data, but no one connects it into decisions. |
| **POS/ERP provider** (PesoWeb, our own SaaS) | Sells to thousands of tenants and cannot test every edge case, volume or business type before customers hit it. |

### Problem 1: Stores are managed by product, not by customer mission

A shopper at 6 PM is on an "after-work top-up" mission, and a shopper at 7 AM is on a "grab-and-go breakfast" mission. Product-level reports hide this, so stocking, pricing and bundling decisions are guessed. The data (sales, inventory, reviews, support) sits in separate places.

### Problem 2: Operational leaks are found late

Cash that doesn't balance at close, inventory that doesn't match the shelf, stock that expires unsold, abnormal refunds and short deliveries are typical retail losses. Basic POS alerts (low stock, expiry date) catch some of them. Many are noticed only after the money is lost, and the cause is unclear ("is it theft, error, or process?").

### Problem 3: Testing retail software with static mock data misses all of it

Mock data cannot reproduce habits, repeat customers, surges, supplier delays or a cashier with an unexplained cash-out. Teams therefore cannot answer: *"If this were a real business, would our system notice what is going wrong, and could it handle the volume?"*

## Our solution

Two things built together:

1. **Sim.PesoWeb**: a synthetic retail world. Simulated business owners sign up to the real PesoWeb, pick a plan, open branches, hire staff and load products. Simulated customers with persistent personalities (many archetypes, thousands to millions of individuals) then shop there. Three modes: **Quick Sim** (fast-forward at scale), **Day-to-Day** (virtual users operate the real system), **Scenario Sim** (inject a demand spike, supplier delay, cash shortage, expiry batch).
2. **MissionCommerce AI**: the intelligence on top. It detects customer **missions** from time, basket and branch signals, forecasts demand with a real statistical/ML model, and recommends actions (assortment, stock, price, bundles, transfers, purchase orders). It also investigates incidents the system missed and explains them with evidence. A language model explains and orchestrates; it is **not** the forecasting method.

AMD runs the real workload: vLLM on ROCm for the investigator and generators, PyTorch on ROCm for forecast, mission and anomaly models, and GPU event generation for scale, with `rocm-smi` and throughput shown live.

## What we measure (hypotheses, not claims)

We state these as what the demo will test, and report the real numbers from the runs, whatever they are.

| Loop | Measure | How |
|---|---|---|
| Growth | Sales, waste and margin, Week 0 vs Week 3 | Same seed run twice, with and without the AI's actions |
| Growth | Mission detection precision and recall | Scored against the simulator's known customer missions |
| Growth | Forecast error vs a naive baseline | Held-out simulated week |
| Protection | Detection coverage: injected incidents the system caught, the AI found, or no one found | Ground truth recorded at injection |
| Scale | Events per second, virtual-days per second on AMD | Measured on the aggregated lane |

## Why this fits the track

| Track criterion | Where it is addressed |
|---|---|
| A real customer or merchant problem | Cash variance, shrinkage, expiry loss, mission-blind stocking |
| A useful commercial action | Assortment, stock, price, bundle, transfer and purchase recommendations; incident explanations |
| Relevant recommendations | Mission-aware, vertical-aware (convenience, grocery/pharmacy, motorcycle parts) |
| A measurable effect | Week 0 vs Week 3 KPIs; detection coverage |
| Forecasting not LLM-only | Statistical/ML forecast, with the LLM as explainer |
| AMD is meaningful and visible | vLLM, PyTorch and event generation on AMD Instinct via ROCm |

## Scope and honest limits

- Simulated data tests **detection and scale**. It does not prove real-world accuracy or predict real markets.
- Quick Sim at scale is **aggregated** and labelled as such. Day-to-Day and Scenario runs go through the real PesoWeb APIs.
- Customer and owner populations are plausible, built from LLM archetypes plus constraints, and not calibrated against real customer data.
- Variances are reported as **unexplained cash variance**, never as an accusation of theft.
- Out of scope for this submission: online reserved orders, self-pickup, work orders, complaint desk, procurement quality, electronics-specific serial/warranty tracking.

## Submission text drafts

**Short description**
MissionCommerce AI finds what customers are trying to do in a store and what the POS misses, and Sim.PesoWeb proves it by running the real system inside an AI-generated retail world on AMD.

**Long description**
Retailers sit on sales, stock and cash data but manage stores by product, not by customer mission, and they discover leaks such as cash variance, shrinkage and expired stock only after the loss. Static mock data cannot test for any of it. We built Sim.PesoWeb, a synthetic retail world where simulated business owners sign up to our real PesoWeb POS/ERP, open branches and hire staff, and simulated customers with persistent personalities shop there in three modes: Quick Sim at scale, Day-to-Day with virtual users operating the real system, and Scenario Sim with injected events. On top, MissionCommerce AI detects customer missions, forecasts demand with a statistical/ML model, recommends commercial actions, and investigates incidents the system missed. Every injected incident is scored as caught by PesoWeb, found by the AI, or undetected, and the same seeded run is compared with and without the AI's actions. Forecast, mission and anomaly models and the LLM investigator run on AMD Instinct with ROCm, with live GPU metrics in the demo. Results come from real runs, and we state the limits of simulation openly.

# The concept, explained with real data

Companion to `concept-demo-guide.md` (how to run it). This page answers: what is MissionCommerce AI trying to do, what do the data look like before and after each feature, how does the AI think, where does it learn, and which exact part of the program takes actions. Every number below comes from a real run (the demo script, or recorded runs in `results/`).

---

## 1. The objective

A shop owner loses money in four quiet ways. MissionCommerce AI is the layer on top of the POS (PesoWeb) that stops each one, and Sim.PesoWeb is the practice shop that lets us prove it before a real shop is involved.

| Objective | What the AI does | Built and measured? |
|---|---|---|
| **Cut waste** from expiring stock | Marks down batches that will not sell before they expire (the headline feature) | Yes. Demo and 5-seed proof |
| **Protect margin** | Never prices below the owner's floor; PesoWeb enforces it, not the AI | Yes |
| **Find leaks the POS cannot see** (short deliveries, silent stock loss) | Chooses where to count stock, and flags counts that come back short | Yes (found 2 of 2 invisible incidents with enough counts) |
| **Real-time agility** | Re-checks every hour and reacts to what sold so far | Yes (hourly agent) |
| **Understand customer missions** (why people shop: after-work top-up, urgent medicine...) | Detect missions from time, basket and branch | **Not built yet.** It is in the design only |

---

## 2. The loop, and which part acts

```
 SHOP DATA (PesoWeb)        THINK (AI, ai/missionai)                 ACT (only one place)            RULES (PesoWeb)
 expiry + stock    ──►  demand.py      "how fast does it sell,   agent.py  ──►  POST /api/Pricing/Markdown ──► checks guardrails
 sales history          how does price  how does price change     (MarkdownAgent)   (source = Ai)                 applies or refuses
 policy (owner's        change that?"   that?"                    posts ONE price                               writes ledger row
 rules)                 optimizer.py    "which discount is        request per batch                             the POS charges it
                        best?"                                           ▲                                              │
                        recorder.py     writes the prediction            │                                              │
                        down BEFORE ◄───────────────────────────────────┘                                              │
                        explain.py      plain-words reason                                  next hour: sales come back ◄┘
```

| Question | Answer | Where in the code |
|---|---|---|
| Who **thinks**? | A small statistical model plus a search over discounts. No LLM involved | `ai/missionai/demand.py`, `optimizer.py` |
| Who **acts**? | Exactly one function posts a price change: `MarkdownAgent._post`, called from `tick` each hour | `ai/missionai/agent.py` -> `PesoWebDriver.markdown` -> `POST /api/Pricing/Markdown` |
| Who can **say no**? | PesoWeb (owner's rules). The agent cannot override it | `PricingController` -> `MarkdownService` -> `MarkdownGuardrails` in PesoWeb |
| Who **remembers**? | The recorder (agent side) and PesoWeb's price-change ledger | `recorder.py`, table `PriceChanges` |
| Who **explains**? | A template sentence; an LLM may reword it, never decide | `explain.py` |
| Who **finds invisible incidents**? | The detector ranks where to count; a count that comes back short becomes a finding | `detectors.py` (plus PesoWeb's stock count API) |

---

## 3. Before and after, feature by feature (sample data)

### Feature 1. Expiry stock sold first-expiry-first-out (FEFO)

Before the agent (data PesoWeb holds for the demo shop, product "Fresh Milk 1L", cost 60, price 100):

| Batch | Quantity | Expires | Sells first? |
|---|---|---|---|
| LOT-TOMORROW | 40 | tomorrow | **Yes** (FEFO: nearest expiry goes first) |
| LOT-LATER | 40 | in 20 days | after the first is gone |

Output to the cashier: a customer buys 1 unit and the POS charges **100.00**, taken from LOT-TOMORROW (so 39 are left there). PesoWeb's expiry feed lists LOT-TOMORROW as `Critical` with money at risk 39 x 60 = **2,340 pesos**.

### Feature 2. The owner's rules (guardrails)

| Setting | Value | Meaning |
|---|---|---|
| Autonomy | Autonomous | The agent may act on its own inside the limits |
| Hard floor | cost + 5% = **63.00** | Never below this, cannot be waived |
| Soft floor | cost + 10% = 66.00 | Below this needs a human approval |
| Max discount | 50% | Never deeper than half price |

### Feature 3. The agent's decision (this is the "thinking")

The agent knows: 39 units left in tomorrow's batch, about 12 sell per day, and it assumes a price slope of -1.5 (cheaper sells more). For each discount it predicts how many units sell before expiry:

| Discount | Price | Expected units sold (range) | Units wasted | Revenue | Allowed? |
|---|---|---|---|---|---|
| 0% | 100 | 12.0 (8 to 16) | 27 = 1,620 pesos | 1,200 | yes (do nothing) |
| 10% | 90 | 14.1 (9 to 19) | 25 = 1,497 pesos | 1,265 | yes |
| 20% | 80 | 16.8 (12 to 22) | 22 = 1,334 pesos | 1,342 | yes |
| **30%** | **70** | **20.5 (15 to 26)** | **19 = 1,111 pesos** | **1,434** | **yes, best allowed** |
| 40% | 60 | 25.8 (19 to 32) | 13 = 791 pesos | 1,549 | blocked: 60 is below cost + 5% (63) |
| 50% | 50 | 33.9 (26 to 39) | 5 = 304 pesos | 1,697 | blocked: below cost |

Rule it follows: pick the allowed discount with the best money outcome (revenue minus what was paid for the batch, which equals margin on units sold minus the write-off of leftovers). It also requires the gain over doing nothing to be real (at least 1 peso and 1%). Result: **30% off, price 70**. It writes the prediction down first (`p-1`: expect 20 units, range 15 to 26, about 1,111 pesos wasted; doing nothing: 1,620).

### Feature 4. PesoWeb applies it (the action and the proof)

| | Before | After |
|---|---|---|
| POS price for tomorrow's batch | 100.00 | **70.00** |
| `PriceChanges` row | none | `100.00 -> 70.00, Applied, Source=Ai, PredictionRef=p-1` |
| `ActiveMarkdowns` row | none | `batch LOT-TOMORROW, price 70.00, active` |

The unsafe request (80% off = price 20):

| Request | PesoWeb's answer | Shelf price afterwards |
|---|---|---|
| Price 20 for the same batch | HTTP **422**, `EXCEEDS_MAX_DISCOUNT: Discount exceeds the maximum of 50.00%` | still 70.00 |
| Ledger | `100.00 -> 20.00, Rejected, EXCEEDS_MAX_DISCOUNT` | |

### Feature 5. Prediction versus what really happened

Recorded predictions from a real run (agent applied markdowns, then the day played out in PesoWeb). "Real" is what PesoWeb's batch quantities showed afterward:

| Batch | Discount | Quantity | Predicted units sold | Range | Units if no markdown | **Real units sold** |
|---|---|---|---|---|---|---|
| p-1 | 20% | 16 | 15.1 | 10 to 16 | 10.0 | **16** (sold out) |
| p-3 | 20% | 18 | 18.0 | 13 to 18 | 11.0 | **18** (sold out) |
| p-5 | 30% | 4 | 1.7 | 0 to 3 | 1.0 | **4** (sold out) |
| p-6 | 10% | 11 | 9.8 | 6 to 11 | 6.5 | **11** (sold out) |

Reading it honestly: the markdowns worked (every batch sold out, while the no-markdown guess says about 6 to 11 units would sell). The predictions are a little pessimistic in this run, and over five seeds the agent's predicted waste was more than twice the real waste (34.9k predicted, 15.9k real). That gap is measured and shown, not hidden.

### Feature 6. Finding what the POS cannot see

Before (PesoWeb alone, 5 incidents injected into the practice shops):

| Incident | PesoWeb alone |
|---|---|
| Cash drawer short by 100 and 400 | **Caught** ("Unexplained cash variance of -100 on shift 9") |
| Short-dated batch delivered | **Caught** (expiry alert on that exact batch) |
| Delivery that arrived 7 units short, no receiving report | Missed |
| 3 units gone from the shelf, nothing recorded | Missed |

After the AI spends a counting budget on risk-ranked SKUs (deliveries without a receiving report first, then high-value fast movers):

| Counting budget | Caught by PesoWeb | Found by AI | Missed | Coverage |
|---|---|---|---|---|
| none | 3 | 0 | 2 | 60% |
| 4 SKUs per branch | 3 | 1 ("count differs from system by 7 unit(s) after a delivery with no receiving report") | 1 | 80% |
| 8 SKUs per branch (all) | 3 | 2 | 0 | 100% |

More counting finds more, and counting costs labor; that trade-off is the honest result.

### Feature 7. Scale lane (Quick Sim)

200,000 simulated shoppers for 28 days, generated in seconds (about 280,000 events per second on a laptop CPU). A price-aware forecast made 16.3% error against 26.7% for "same as last week"; 12 of 12 planted anomalies were found with 74 cells flagged. This lane does not go through PesoWeb and is labelled aggregated.

---

## 4. Where does the AI learn? (and is it reinforcement learning?)

**Honest answer: it is not reinforcement learning today.** Here is exactly what exists:

| Piece | Kind of learning | Where | Used in the 1-minute demo? |
|---|---|---|---|
| Price response ("how many more sell if the price drops?") | **Statistical learning** (Poisson regression with a prior), fitted from real sales that happened at different prices | `demand.py`, fitted by `AiHooks.run_history` in `sim/simpeso/ai_hook.py` | **No.** The demo has no sales history, so it uses a starting guess (slope -1.5) |
| Hour-of-day pattern (how much of a day's sales are still to come) | Statistical learning from the sales ledger | `DemandModel.fit_hours` | No (uniform guess) |
| Prediction scoring (was the guess right?) | **Feedback measured, not yet fed back automatically** | `recorder.py` (`calibration()`) | Yes, the prediction is recorded |
| Choosing the discount | **Planning** with the learned model: try each allowed discount, pick the best predicted outcome. One step ahead, no trial and error | `optimizer.py` | Yes |

What learning looks like with sales history (real, from a recorded run: starting guess -1.3 for every category, then learned from four promo days):

| Category | Before (starting guess) | After learning | Observations used |
|---|---|---|---|
| Chilled drinks | -1.30 | **-3.30** | 8 |
| Ready meals | -1.30 | -2.04 | 3 |
| Fresh dairy | -1.30 | -1.12 | 1 |
| Fresh produce | -1.30 | -1.30 (no data, stays at the guess) | 0 |

A more negative number means "very sensitive to price". The ridge prior keeps the number close to the guess when there is little data, but with only 1 to 10 observations per category these estimates are still noisy (one category jumped to -4.29 on two observations). That is one reason the agent's predictions are not yet well calibrated.

**Where reinforcement learning would fit (not built):** the recorder already stores, for every markdown, the situation (stock, hours left), the action (discount) and the outcome (units sold, waste, margin). That is exactly the (state, action, reward) data a learning loop needs. The natural next step is a *contextual bandit* over the discount ladder (try a discount, observe the reward, shift toward discounts that earn more), with the reward = realized net money. It is safe to try because the action space is already fenced by PesoWeb's guardrails: the agent can explore only prices the owner allows. We have **not** built or measured this, and we do not claim it.

**The simulator's role in learning:** the practice shops give the AI thousands of safe "days" with known ground truth (we know what really happened and what incident was injected), so any learning step can be tested without risking a real shop. The shoppers' true price response is hidden from the AI on purpose, so what it learns is learned, not copied.

---

## 5. How to reproduce each output

| Output | Command |
|---|---|
| Features 1 to 5 (the demo) | `python demo/concept_demo.py` |
| Feature 5 table, learning table, three-way comparison | `cd sim && python -m simpeso.proof --seeds 1-5 --out ../results/proof-smoke.json` (needs the root password env var, see `sim/README.md`) |
| Feature 6 | `cd sim && python scripts/export_results.py --what incident` |
| Feature 7 | `cd sim && python -m simpeso.quicksim --device auto` |
| All of it, visually | `python -m http.server 8080` from the repo root, open `/ui/dashboard/` |

## 6. One-paragraph summary for anyone new

PesoWeb is the shop's computer. We added a helper that watches for stock about to expire, guesses how many will sell at different prices, writes the guess down, and asks PesoWeb for a lower price. PesoWeb, following the owner's rules, accepts safe prices and refuses unsafe ones. The helper learns how price-sensitive customers are from past sales, and we check its guesses against what really sold. We tested it in a simulated group of shops: it clearly beats doing nothing, and it is currently about as good as a simple fixed discount rule, not better. Reinforcement learning is a planned next step, not something that exists yet.

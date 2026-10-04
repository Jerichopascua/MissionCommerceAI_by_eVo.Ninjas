# Plan 5: AI core (demand response, markdown agent, prediction recorder, detectors, explainer)

> Compact format: interfaces and test lists are binding, bodies are not. Executed autonomously with the owner's standing approval (2026-10-05); nothing is pushed or published.

**Goal:** a CPU-runnable Python package `ai/missionai` that (1) learns price response from observed sales, (2) chooses markdowns for at-risk batches and executes them through the real PesoWeb pricing API within PesoWeb's guardrails, (3) records a prediction before every markdown and scores it against what happened, (4) finds the two incidents PesoWeb cannot see (unreported short delivery, hidden shrink) by risk-ranked stock counts, and (5) explains decisions in plain words (template always; vLLM optional). The same code runs unchanged on the AMD box; only the optional explainer endpoint differs.

**Exit test:** on the throwaway PesoWeb database, the agent (a) applies markdowns that PesoWeb accepts, refuses an unsafe one with a guardrail code, and records predictions that resolve to realized outcomes; (b) the day's scorecard moves from 3 caught / 2 undetected to 5 of 5 covered with at least one `ai_found`.

## Constraints

- Python stdlib + numpy only for the models (no sklearn dependency), so unit tests run anywhere. `requests` only inside the sim driver.
- The AI never imports `simpeso.behavior`, `archetypes`, or reads shopper elasticity. A test greps for it. It sees only what a tenant tool can read from PesoWeb (sales events, expiry risk, receipts, exceptions) plus its own actions.
- The LLM is never in the decision path. `explain.py` returns a template sentence when no endpoint is configured or the call fails.
- Guardrails belong to PesoWeb. The agent respects `autonomyMode` (Off = do nothing, ApprovalRequired = propose and stop at 202) and treats 422 as information, not as something to retry around.
- Wording: variances stay "unexplained"; findings say "count differs from system", never an accusation.

## Layout

```
ai/missionai/{__init__,demand,optimizer,recorder,agent,detectors,explain}.py
ai/tests/test_*.py
sim/simpeso/ai_hook.py     glue: price ratios from active markdowns, hourly agent ticks, count executor, history seeding
```

## Binding interfaces

```python
demand.DemandModel(prior_beta=-1.3, prior_weight=8.0)
  .observe(category, base_rate, ratio, units)        # one observation window
  .beta(category) -> float                           # ridge-shrunk Poisson MLE of the log-price slope
  .fit_hours(hour_units: dict[int, float]); .share_left(hour) -> float   # share of daily units still to come
  .expected_units(category, base_per_day, ratio, days_left, hour) -> (mean, lo, hi)
optimizer.choose(batch, policy, model, ladder=(0, 10, 20, 30, 40, 50)) -> Decision
  # maximise expected revenue minus sunk cost (= margin of sold units minus write-off of leftovers); respects max discount and
  # the hard/soft margin floors on NET price; returns the prediction (units mean/lo/hi, margin, waste pesos) with the discount
recorder.PredictionRecorder(path).record(decision) -> id ; .resolve(id, realized_units, avg_price) ; .calibration() -> dict
  # MAE units, interval coverage, margin error, and the same measures for a naive predictor (assume no markdown helps: units = base)
agent.MarkdownAgent(client, model, recorder, explainer).tick(hour) -> list[Action]
  # per branch: read policy and expiry risk, decide, post markdown (source=Ai, predictionRef), handle 200/202/422, rate-limit per SKU
detectors.rank_count_targets(receipts, exceptions, sales_units, k) -> list[Target]   # risk score per branch and SKU
detectors.findings_from_counts(results, receipts) -> list[dict]   # {id, type, branch, evidence}; type inferred, then scored against truth
explain.explain(decision, outcome, endpoint=None) -> str
```

## Tasks

- [x] **Task 1: DemandModel.** Scalar Poisson log-slope per category with a ridge prior (cold start uses the prior), hour profile, expected units with an interval. Tests: recovers a planted elasticity within 0.25 from synthetic Poisson data; with no data returns the prior; shrinkage pulls a noisy small sample toward the prior; categories are independent; interval contains the mean and widens with the mean; `share_left` is 1 at open, 0 after close and monotone.
- [x] **Task 2: Optimizer.** Ladder search over discount steps. Tests: overstocked near-expiry batch gets a deeper discount than a lightly stocked one; never exceeds `maxDiscountPct`; never prices below the hard floor on net price (cost known); respects Product.Discount in the net price; no markdown when stock will sell anyway; deterministic; returns a prediction whose margin and waste match the arithmetic.
- [x] **Task 3: Recorder and calibration.** JSONL store; resolve with realized units; calibration vs the naive predictor. Tests: round trip, resolve twice rejected, MAE and interval coverage exact on a hand case, naive baseline computed, empty store is safe.
- [x] **Task 4: Agent.** Fake-client unit tests plus live. Tests: Off mode posts nothing; ApprovalRequired stops at 202 and records the pending change; 422 is logged with its guardrail code and not retried at a lower price automatically; the rate limit is respected; each qualifying batch gets exactly one recorded prediction; an unchanged decision posts nothing.
- [x] **Task 5: Sim glue.** Driver gets `set_policy`, `markdown`, `expiry_risk`, `receipts`, stock count calls; runner builds hourly price ratios from `ai/active-markdowns` so shoppers see marked-down prices; opening stock can be set to "last-day" perishables (days left 1) for the markdown trial; history seeding runs a few promo days so the model has price variation to learn from. Tests: ratio map built from rows, count executor reports system minus recorded physical loss, history seeding is deterministic.
- [x] **Task 6: Detectors.** Risk-ranked counts. Tests: a delivery without a receiving report outranks one with a report; high value outranks low value; k respected; a count variance beyond tolerance produces a finding with the inferred type; matched counts produce none; a duplicate finding is not emitted twice.
- [x] **Task 7: Explainer.** Template sentence from decision and outcome; optional OpenAI-compatible call with a short timeout and a safe fallback. Tests: template covers discount, units, guardrail refusal; endpoint failure falls back; no call when endpoint is None.
- [x] **Task 8: Live verification and package.** Start PesoWeb (new build), build a `smoke` world, run history seeding, run the markdown trial day with the agent, run detectors, score. Update README, spec, execution log, export PesoWeb patch for the receipts endpoint to `pesoweb-additions/patches/plan5`, commit.

## Exit criteria

- All unit tests pass (`python -m unittest discover -s ai/tests -t ai` and the sim suite).
- Live: markdowns applied by the agent are visible in `ai/active-markdowns` and change what shoppers pay; one unsafe proposal is refused with a guardrail code; predictions resolve; the scorecard reports `ai_found` for the invisible incidents.
- The calibration report shows the model against the naive predictor, whatever the numbers are.

## Not in this plan

Three-way proof runs with fixed-rule baseline at scale, Quick Sim GPU lane, mission-detection model, UI (Plan 6).

## Execution log and results

Built 2026-10-06 (autonomously, on the owner's standing approval). 64 AI tests and 63 sim tests pass. PesoWeb gained three read-only feeds (`patches/plan5`; 119 PesoWeb tests still pass). Live runs used the throwaway database, `smoke` world (5 companies, 12 branches, 8 products each), seed 21, one trial day. Every number below comes from those runs; each configuration is a single seeded day, so treat them as a first reading, not a measured effect size (multi-seed runs are Plan 6).

**Markdown agent (trial day, short-dated perishable lots sized at 1.6 days of demand, autonomous pricing):**

| Setup | Markdowns applied | Refused by PesoWeb | Waste at day end | Units sold | Revenue |
|---|---|---|---|---|---|
| Agent off | 0 | 0 | 19,647 pesos | 476 | 135,414 |
| Agent on, hard floor 10%, soft floor 20% (first config, thinner stock) | 13 | 0 | 18,426 pesos (-6%, against 19,663 off) | 501 | 136,281 |
| Agent on, hard floor 0%, soft floor 5% | 41 | 5 (`TOO_MANY_CHANGES`) | 11,138 pesos (-43%) | 654 | 142,917 |

The margin floors decide how much the agent can do: with a 20% soft floor most ladder steps are blocked because many items only carry 20 to 25% margin. Margin per unit falls as units rise, so a margin comparison (revenue minus cost of goods sold) is still owed in Plan 6.

**Prediction quality (agent on, 19 resolved predictions, floors 0/5):** units error 2.6 against a naive 3.96 in the first run but only a 3% skill in later runs, 68% of outcomes inside the 80% interval, **predicted waste 5,812 pesos against 10,152 realized**. The model is optimistic about how much a markdown sells; the learned price slopes came from only four promo days and are noisy (for example snacks -0.89, chilled drinks -2.4). That is reported as it is: calibration is mediocre, and improving it (more history, per-product slopes, a tighter interval) is Plan 6 work.

**Incident finding (counting budget per branch):**

| Budget | Caught by PesoWeb | Found by AI | Undetected | Coverage |
|---|---|---|---|---|
| none (Plan 4) | 3 | 0 | 2 | 0.6 |
| 4 SKUs per branch | 3 | 1 (unreported short delivery) | 1 (hidden shrink) | 0.8 |
| 8 SKUs per branch (every SKU in the smoke world) | 3 | 2 | 0 | 1.0 |

So coverage rises with counting effort, which is the honest trade-off: the AI finds what a count can reveal, and counts cost labor. PesoWeb's own alerts fired 54 to 87 times on those runs (mostly expiry alerts and negative stock), against 2 real findings from the AI.

**Corrections found by running it live:**
- `Expiry/Risk` lists only batches inside the alert window; promos and shopper prices need every stocked batch, hence `/api/ai/batches`.
- The delivery detector first labelled every short count as an "unreported short delivery" because each SKU's first (onboarding) purchase has no receiving report. Opening stock is now excluded; a test covers it.
- Findings were overwritten by a second pass; they now accumulate by id.
- Opening stock was too small, so non-expiry products went negative (-8) and a negative system balance hid a real shortfall; opening stock is now 25 days of estimated demand (minimum 30).
- Shoppers now decide their basket at the time they shop, at the prices in force that hour (`behavior.day_arrivals` plus `fill_basket`), so an hourly markdown actually changes what is bought.

**Known gaps (carried to Plan 6):** the world never restocks, so only one-day trials are meaningful; no fixed-rule baseline arm yet; realized price is approximated by the applied discount; one seed per configuration; per-shopper PesoWeb customers; mission detection; the optional vLLM explainer has not been exercised on AMD (the template is used everywhere).


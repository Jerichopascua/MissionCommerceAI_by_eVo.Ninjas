# MissionCommerce AI core (`ai/missionai`)

Pure Python (stdlib only), CPU-runnable, 64 unit tests: `cd ai && PYTHONPATH=. python -m unittest discover -s tests -t .`

| Module | What it does |
|---|---|
| `demand.py` | Price response learned from observed sales: a Poisson log-price slope per category under a ridge prior (stays near the prior with little data), plus an hour-of-day profile. |
| `optimizer.py` | For one at-risk batch, picks a discount from a bounded ladder that maximises expected revenue minus sunk cost (margin on units sold minus write-off of leftovers), respecting max discount and the hard and soft margin floors on net price and the FEFO queue ahead of the batch. |
| `agent.py` | Hourly: reads the tenant's policy and expiry risk, decides, records the prediction **before** acting, posts the markdown to PesoWeb as `source=Ai`, and handles 200 (applied), 202 (waiting for approval) and 422 (refused, with the guardrail code). Never retries a refusal at a lower price. Autonomy `Off` does nothing. |
| `recorder.py` | Prediction store and calibration against a naive predictor that ignores the markdown. |
| `detectors.py` | Ranks stock counts by risk (deliveries without a receiving report first, then value and velocity) and turns a short count into a finding worded "count differs from system". Each SKU's first receipt is opening stock, not a delivery. |
| `explain.py` | Plain-words template for every decision; optional OpenAI-compatible (vLLM) rewrite with a short timeout and a safe fallback. The LLM is never in the decision path. |

The AI sees only what a tenant tool can read from PesoWeb (`Expiry/Risk`, `/api/ai/batches|movements|receipts`, `Pricing/*`, `StockCounts/*`) plus its own actions. Tests fail if the package imports the simulator or the hidden shopper response, or if anything but `explain.py` can make a network call. Glue to the simulator is `sim/simpeso/ai_hook.py`.

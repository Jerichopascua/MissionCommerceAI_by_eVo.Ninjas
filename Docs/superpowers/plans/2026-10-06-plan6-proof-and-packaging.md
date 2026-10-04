# Plan 6: Proof, Quick Sim, dashboard and packaging

Executed autonomously 2026-10-05/06 on the owner's standing approval. Compact record; results below come from recorded runs in `results/`.

## Delivered

- **Three-way proof** (`sim/simpeso/proof.py`): same seeded world with no markdown, a fixed last-day rule (30% off, falling back to 20 and 10 if PesoWeb refuses) and the AI agent. Margin and net after waste are tracked (cost of goods from the sim, waste from PesoWeb batch quantities) with paired comparisons over seeds. `FixedRuleHooks` is the baseline.
- **Quick Sim** (`sim/simpeso/quicksim.py`): torch lane with persistent individuals, planted promos and anomalies, a price-aware forecast against seasonal naive, a dispersion-calibrated anomaly detector, and a throughput report. Runs on CPU or any CUDA/ROCm device.
- **Dashboard** (`ui/dashboard/index.html`) reading `results/*.json`; `sim/scripts/export_results.py` builds the incident and action files.
- **Packaging**: README, MIT license, Dockerfile and compose (not built here: no Docker on this machine).

## Results (smoke world, 5 seeds, floors 0% / 5%)

| | None | Fixed rule | AI |
|---|---|---|---|
| Waste (mean pesos) | 20,293 | 8,034 | 8,419 |
| Margin (mean pesos) | 47,795 | 46,730 | 46,685 |
| Net after waste (mean pesos) | 27,502 | 38,696 | 38,266 |
| Units sold (mean) | 692 | 991 | 949 |
| Markdowns applied / refused | 0 | 32 / 8 | 32 / 4 |

AI vs none: waste -11,874 pesos (better on 5 of 5 seeds), margin -1,110 (0 of 5, because markdowns trade unit margin for volume), net +10,764 (5 of 5). AI vs fixed: waste +385 (better on 2 of 5), net -430 (3 of 5). **No demonstrated advantage over a sensible fixed rule in this setup.**

Calibration: 159 resolved predictions, units MAE 3.2 vs naive 6.5, 73% of outcomes inside the 80% interval, predicted waste 34.9k vs realized 15.9k (too pessimistic, the opposite of the first single-seed run).

Quick Sim (CPU, 200,000 individuals, 28 days): about 280,000 events per second, forecast error 16.3% vs 26.7% naive, 12 of 12 planted anomalies found with 74 flagged cells.

## Honest reading and next steps

The setup favors a flat rule: every lot is sized at 1.6 days of demand, margins are uniform, and demand is smooth, so one discount fits most lots. The agent's potential edge (a different discount per lot, reacting during the day) needs heterogeneous stock levels, tighter margin floors and noisier demand to show, and its predictions need recalibration (per-product slopes, more promo history). That is not claimed anywhere until measured.

Still open: restocking and multi-day horizons, per-shopper PesoWeb customers, mission detection, the vLLM explainer and the Quick Sim GPU run on AMD, and building the container image.

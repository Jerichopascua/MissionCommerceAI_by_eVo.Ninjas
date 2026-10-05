# Review guide: what to look at, in 15 minutes

## What is running right now (started for your review)

| What | Address | Notes |
|---|---|---|
| PesoWeb (the shop system, local dev database `PesoWeb_MissionDev`) | http://localhost:5071 | needs SQL Server LocalDB running |
| Results dashboard | http://127.0.0.1:8080/ui/dashboard/ | static page reading `results/*.json`; started with `python -m http.server 8080 --bind 127.0.0.1` from the repo root |

If they are not running (after a restart): start PesoWeb as in `concept-demo-guide.md` Step 1, then run the `http.server` command above.

## Review in this order

1. **The simple concept (3 min).** `python demo/concept_demo.py` (output also saved in `results/concept-demo-output.txt`). One shop, one expiring milk batch, one AI decision, PesoWeb applies a safe price and refuses an unsafe one. Expect `9 of 9 checks passed`. Explanation with data: `concept-demo-explained.md`; run and proof steps: `concept-demo-guide.md`.
2. **The customer story (5 min).** `cd sim && python -m simpeso.story --arm learning --days 12 --seed 3` prints Marco's diary (your chicken story) and "what the system saw". Explanation and numbers: `customer-actors.md`. Open the dashboard, top panel "Customer story".
3. **The measured proof (3 min).** Dashboard panels "Waste vs no markdown" and "Agent decisions and guardrails". Five seeds: the AI beats doing nothing on all five, and ties a simple fixed rule. Source: `results/proof-smoke.json`.
4. **Incidents and scale (2 min).** Dashboard panels "Caught vs missed" (PesoWeb alone 60%, AI counts raise it to 80% then 100%) and "Quick Sim" (200,000 shoppers x 28 days).

## What to challenge (the honest weak spots)

- The customers' judgement is a rule-based model we wrote, not an LLM and not measured human behavior. Is that realistic enough for the demo, or should a few hero customers be driven by an LLM?
- The AI is **not** better than a plain "30% off on the last day" rule in the measured proof. Where would a real shop need something smarter (different products, different margins, noisy demand)?
- Predicted waste was off by a factor of two in the five-seed proof. Acceptable to show as is?
- There is no reinforcement learning yet. The recorded decisions and outcomes are the data it would need; a bandit over the discount ladder (or over the clearance hour) is the natural next step.
- Customer missions (why people shop) are in the design but not built.
- Still on your side: AMD instance tests (`amd-setup-guide.md`), Quick Sim and the optional LLM explainer on the GPU, the "built during the event" question for the organizers, Docker image never built.

## Where things are

| Need | File |
|---|---|
| Overall story, limits, layout | `readme.md` |
| Concept demo: run, prove, explain | `Docs/concept-demo-guide.md`, `Docs/concept-demo-explained.md` |
| Customer actors and the chicken story | `Docs/customer-actors.md` |
| Plans, results logs, findings | `Docs/superpowers/plans/` |
| Raw results | `results/` |

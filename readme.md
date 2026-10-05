# MissionCommerce AI + Sim.PesoWeb

Team Evo.Ninjas | AMD Developer Hackathon: Act III | Track 3: Reinvent Commerce

Retailers find out about waste, cash leaks and stock loss after the money is gone, and they cannot test fixes safely before real stores see them. This repo has two parts built together:

- **Sim.PesoWeb**: a seeded synthetic retail world. A corporate group of five companies (tenants) signs up to the real **PesoWeb** POS/ERP through its API, opens branches, hires staff, loads catalogs with expiry dates, and is visited by persistent shoppers. Branches open mid-run. Incidents are injected with ground truth.
- **MissionCommerce AI**: agentic markdown pricing for short-dated stock (the headline), prediction scoring, and finding the incidents the POS cannot see. PesoWeb enforces the guardrails; the agent cannot override them, and a language model never makes a decision.

## What the runs show

Numbers are from recorded runs in `results/` (small `smoke` world, one trial day of short-dated perishable lots, 5 seeds). Details and the per-seed table are on the dashboard.

| | No markdown | Fixed rule (30% off last day) | AI agent |
|---|---|---|---|
| Waste at day end (mean, pesos) | 20,293 | 8,034 | 8,419 |
| Net after waste (mean, pesos) | 27,502 | 38,696 | 38,266 |

- The AI beats doing nothing on all 5 seeds (waste -58%, net +10.8k pesos). It does **not** beat a sensible fixed rule in this setup: the two are within noise (AI net -430 pesos, better on 3 of 5 seeds). We report that rather than hide it.
- Prediction quality is mixed: 159 predictions, units error 3.2 against 6.5 for a naive predictor, 73% inside the 80% interval, but predicted waste (34.9k) was more than twice realized waste (15.9k). The model is too pessimistic about how much a markdown sells.
- Incidents: PesoWeb alone caught 3 of 5 injected incidents (cash shortages, a near-expiry batch). Risk-ranked stock counts by the AI found the other two (an unreported short delivery, hidden shrink): coverage 0.6, then 0.8 at 4 counts per branch, then 1.0 at 8. Coverage rises with counting effort.
- Quick Sim (aggregated lane, not through PesoWeb): 200,000 individuals for 28 days at about 280,000 events per second on a laptop CPU; the price-aware forecast has 16.3% error against 26.7% for seasonal naive; all 12 planted anomalies found with 74 flagged cells. The AMD GPU run is still to be recorded (`python -m simpeso.quicksim --device auto`).

## Honest limits

- Shoppers' price response is **our assumption** inside the simulator. The AI never sees it and learns it from sales. The runs show the mechanism, the guardrails and prediction accuracy under that assumption; they are not a claim about real-market lift.
- Small world, one-day trials, five seeds. Not a full-year result. The world does not restock, so only short trials are meaningful.
- Archetype and owner libraries are a hand-written starter set (43 customer archetypes), standing in for an LLM-generated library. The LLM explainer is optional and has not been exercised on AMD yet.
- Variances are "unexplained", never an accusation.

## Layout

| Path | What |
|---|---|
| `sim/` | Simulator: world planner, behavior, `PesoWebDriver`, day runner, incidents and scoring, Quick Sim, proof harness (81 tests) |
| `ai/missionai/` | Demand response, markdown optimizer and agent, prediction recorder, detectors, explainer (64 tests) |
| `pesoweb-additions/` | The PesoWeb patches (per plan), SQL scripts, smoke scripts, README for a live test database |
| `Docs/customer-actors.md` | Customer actors with memory and judgement (the chicken story), with results |
| `ui/dashboard/` | Results dashboard (reads `results/`); `ui/prototype/` is the early design mock |
| `results/` | Recorded run outputs the dashboard reads |
| `Docs/` | Problem statement, spec and plans (`Docs/superpowers/`), AMD setup guide, onboarding contract |

## Run it

PesoWeb is the system under test and runs separately (recipe: `pesoweb-additions/README.md`, "Live verification environment").

    pip install -r sim/requirements.txt
    cd sim && python -m unittest discover -s tests -t .                 # simulator tests
    cd ../ai && PYTHONPATH=. python -m unittest discover -s tests -t .  # AI tests
    cd ../sim && python -m simpeso.quicksim --device auto               # aggregated lane, no PesoWeb needed
    PESOWEB_ROOT_PASSWORD=... python -m simpeso.proof --seeds 1-5 --out ../results/proof-smoke.json
    cd .. && python -m http.server 8080                                  # then open /ui/dashboard/

`Dockerfile` and `docker-compose.yml` are provided but have not been built or run yet.

MIT license. No keys are committed; credentials come from environment variables.

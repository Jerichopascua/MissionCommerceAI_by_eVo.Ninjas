# Sim.PesoWeb (simulator core)

A seeded synthetic retail world that drives the **real** PesoWeb API: a corporate group of five companies (tenants), each with branches, staff and a catalog, visited by persistent shoppers. It injects incidents with ground truth and scores who noticed them. No AI yet: `ai_found` is zero until the MissionCommerce detectors are plugged in.

## Run it

PesoWeb must be running with the Retail_MissionCommerceAI migrations applied (recipe: `pesoweb-additions/README.md`, "Live verification environment"). The central company's root login is only used to raise each subsidiary's plan tier.

    pip install -r sim/requirements.txt
    export PESOWEB_ROOT_PASSWORD=...            # root SuperAdmin of the throwaway database
    cd sim
    python -m simpeso.runner all --seed 21 --profile smoke --run demo1     # build, one day, score
    python -m simpeso.runner build|day|score --run demo1                   # or step by step
    python -m unittest discover -s tests -t .                              # 58 unit tests

`smoke` = 5 companies, 2 branches each (10 + 2 opened mid-run), 8 products, about 110 sales a day. `starter` = about 17 branches plus 2 mid-run openings, 30 products, about 460 sales a day (26 s on a laptop). Run state (throwaway credentials, ledger, scorecard) goes to `sim/runs/<run>/`, which is git-ignored.

## What happens

1. **world** plans the group from `seed + profile`: owners (archetype traits), a vertical per company (convenience, grocery/pharmacy, motorcycle parts, mixed, sports), branches, staff with trait profiles, catalogs, suppliers, one or more mid-run expansions. Everything is clamped to the Business tier limits (5 branches, 10 users) and each clamp is recorded as a decision.
2. **build** registers each owner through `Auth/Register`, lets the central company raise the tier, then creates branches, staff logins, catalog (expiry products with staggered batches) and opening stock through real purchase receipts.
3. **day** steps one business day: staff open cash shifts, shoppers buy through `AddSale` (FEFO and pricing are PesoWeb's), some returns, a new branch opens at its scheduled hour and trades the same day, incidents are injected, shifts close, and PesoWeb's detection pass runs.
4. **score** matches every injected incident to a PesoWeb exception (same branch, mapped type, same amount or batch), then to an AI finding (`ai_findings.json`, written by Plan 5), else `undetected`.

## Honest limits

- Shoppers' price response (elasticity) is our assumption and lives only in `behavior.py`; a test fails if another module reads it. The AI must estimate it from sales.
- Archetype and owner libraries are a hand-authored starter set that stands in for the cached LLM library; validators (grid coverage, near-duplicates, mission fit) apply to both.
- PesoWeb runs on the real clock, so day indexes choose the dice, not the date. Virtual time for multi-day proof runs is Plan 6.
- Incidents `UNREPORTED_SHORT_DELIVERY` and `HIDDEN_SHRINK` are invisible to PesoWeb by design; they exist so the AI has something real to find. Variances are "unexplained", never an accusation.
- Shoppers pay as PesoWeb's default "Cash Customer"; per-shopper customer records (needed for mission detection from loyalty history) are a Plan 5 item.

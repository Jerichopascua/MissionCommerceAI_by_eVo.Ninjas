# Sim.PesoWeb (simulator core)

A seeded synthetic retail world that drives the **real** PesoWeb API: a corporate group of five companies (tenants), each with branches, staff and a catalog, visited by persistent shoppers. It injects incidents with ground truth and scores who noticed them. No AI yet: `ai_found` is zero until the MissionCommerce detectors are plugged in.

## Run it

PesoWeb must be running with the Retail_MissionCommerceAI migrations applied (recipe: `pesoweb-additions/README.md`, "Live verification environment"). The central company's root login is only used to raise each subsidiary's plan tier.

    pip install -r sim/requirements.txt
    export PESOWEB_ROOT_PASSWORD=...            # root SuperAdmin of the throwaway database
    cd sim
    python -m simpeso.runner all --seed 21 --profile smoke --run demo1 --datasets simulated-rules     # build, one day, score
    python -m simpeso.runner build|day|score --run demo1 [--datasets ...]   # or step by step (a day needs --datasets)
    python -m simpeso.datasets                                              # the customer data sets and whether their files are in place
    python -m unittest discover -s tests -t .                              # 63 unit tests

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
- Shoppers pay as PesoWeb's default "Cash Customer"; per-shopper customer records (needed for mission detection from loyalty history) are a Plan 6 item.

## AI pass (`simpeso.ai_hook`, needs the PesoWeb additions from `pesoweb-additions/patches/plan5`)

    sim/scripts/ai_demo.sh <run> on|off [hard-floor] [soft-floor]     # build, incident day, learn, markdown trial, find, score
    python -m simpeso.ai_hook history|trial|find|report --run <run>

`history` runs two baseline days and four promo days (the tenant's own promo calendar) so the model sees price variation. `trial` adds short-dated perishable lots sized at 1.6 days of demand, lets the agent mark them down hour by hour through the real pricing API, and resolves every prediction against what sold. `find` spends a counting budget (`--k` SKUs per branch) on risk-ranked stock counts; the sim plays the physical shelf. Results of the first runs are in `Docs/superpowers/plans/2026-10-06-plan5-ai-core.md`.

## Calibrating against real sales (optional)

    python scripts/calibrate_real.py --db PesoWeb_V2_Real --fit          # reads a restored PesoWeb database, read-only
    python -m simpeso.runner all --datasets simulated-rules --seed 21 --profile smoke --run cal1 --calibration runs/real-calibration.json --calib-weight 0.5

`calibrate_real.py` reads every tenant and branch, reports bootstrap intervals, and writes `runs/real-calibration.json` and `.md` (git-ignored, because they are derived from a real business). `--calibration` blends the real hour-of-day profile into shopper arrivals (weight = how far to trust a small sample) and scales basket size to the real lines per sale. Without the flag nothing changes. Price response is not calibrated: the real sample has too few discounted sales to fit it.

## Using a real product catalog (optional)

    python scripts/extract_real_catalog.py --db PesoWeb_V2_Real --tenants 6,17          # real names, costs, prices, real sales concentration
    python -m simpeso.runner build --seed 21 --profile smoke --run real1 --catalog runs/real_catalog.json --calibration runs/real-calibration.json --policy autonomous

Every company and every branch then sells the real products with their real cost and price (opening stock goes in through purchases of at most 60 lines each, because PesoWeb rejects forms with more than 1,024 values). Best-selling real products pull more shoppers, matching the real concentration. The real source data has no expiry information, so these products are non-expiry: the markdown agent and the near-expiry incident have nothing to act on until perishable lots are added. `runs/real_catalog.json` is git-ignored: it is a real business's product list.


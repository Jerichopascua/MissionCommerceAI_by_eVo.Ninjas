# Plan 4: Sim core (world, behavior, driver, day run, incidents and scoring)

> For agentic workers: execute with superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. Compact format: interfaces and test lists are binding, bodies are not.

**Goal:** a Python service in `sim/` that builds the corporate world through the real PesoWeb API, runs seeded business days of shoppers and cashiers against it, injects incidents with ground truth, and scores them against the Exception Center. Deterministic by seed. No AI yet (Plan 5 adds it); every AI hook is a plain function with a no-op default.

**Exit test (spec P2):** a seeded day runs via real APIs with ground truth recorded, and a new branch opens mid-run. Same seed gives the same action-log hash.

## Constraints

- Python 3.13, `requests`, `pyyaml`, `numpy` (all present). Tests use `unittest` (no pytest installed). No keys committed; base URL and credentials from env or CLI.
- The sim never touches the database directly. It uses only the routes in `Docs/onboarding-contract.md` and Plan 3's APIs. The central company (root `SuperAdmin`) is a normal API client used only to raise a tenant's tier.
- Dice come from `rng.derive(seed, *keys)` (a stable hash of the seed and keys), never from global `random`, so adding a feature does not shift existing streams.
- Hidden price response lives only in `behavior`; nothing outside it may import `elasticity`. A test enforces this.
- Starter profile caps (spec section 3): at most 5 branches per company on Business tier, so group companies use 4 branches plus at most 1 expansion branch. Enterprise tier values stay an open item.
- Honest wording: variances are "unexplained cash variance"; incidents are ground truth in the ledger only.

## Layout

```
sim/
  requirements.txt
  simpeso/{__init__,rng,verticals,archetypes,world,behavior,driver,incidents,scoring,runner}.py
  simpeso/data/verticals/*.yaml   convenience, grocery_pharmacy, motorcycle_parts, mixed, sports
  simpeso/data/customer_archetypes.yaml   owner_archetypes.yaml
  tests/test_*.py
  README.md
```

## Binding interfaces

```python
rng.derive(seed: int, *keys) -> random.Random        # same inputs, same stream
verticals.load_all() -> dict[str, Vertical]; verticals.validate(v) -> list[str]   # [] = valid
verticals.build_catalog(v, rnd, size) -> list[ProductSpec]   # name, code, category, cost, price, expiry profile
archetypes.customer_archetypes() -> list[CustomerArchetype]; archetypes.validate_library(lib) -> list[str]
world.plan_group(seed, profile="starter") -> WorldPlan   # group, 5 companies, owners, branches, staff, catalogs, expansion
world.plan_hash(plan) -> str
behavior.make_individuals(plan, seed) -> list[Individual]   # persistent, named, home branch, wallet, habits
behavior.day_visits(plan, individuals, day, seed, price_ratio=None) -> list[Visit]   # deterministic, price-aware
driver.PesoWebDriver(base_url, run_id)   # register, login, root_set_tier, add_branch, add_staff, add_catalog, receive_stock,
                                         # open_shift, sell, close_shift, return_sale, receiving_report, exceptions, active_markdowns
incidents.plan_incidents(plan, seed, day) -> list[Incident]; incidents.Ledger  # ground truth {id, type, tenant, branch, day, detail}
scoring.score(ledger, exceptions, ai_findings=()) -> Scorecard   # caught / ai_found / undetected per incident
runner: python -m simpeso.runner build|day|score --seed N --profile smoke|starter
```

## Tasks

- [x] **Task 1: Skeleton, seeded RNG, vertical templates.** `rng`, `verticals` with five YAML templates (catalog range, categories with shelf-life profile, margin band, ticket size, expiry on/off, missions, traffic band). Tests: `derive` repeatable and independent per key; every template validates; a template with a margin outside its band, an expiry category without shelf life, or an empty category list fails validation with a message; `build_catalog` is deterministic, respects size and margin band, and sets expiry only for expiry categories.
- [x] **Task 2: Archetypes (customers and owners).** Coverage-grid customer library (age band x income x occupation x household x mobility x time pattern) generating ~40 starter archetypes with a hidden `elasticity` and a mission mix per vertical; owner archetypes (including a conglomerate). Tests: no empty grid cell, no near-duplicates by text similarity, every vertical has missions, library validation catches an injected duplicate.
- [x] **Task 3: World planner.** `plan_group`: central group, 5 companies (vertical mix per company: convenience, grocery/pharmacy, motorcycle, mixed, sports), owners with named traits, business plan constrained by tier limits (branches at most 5, staff within user limit, catalog within product limit), 4 branches per company in `starter` (2 in `smoke`), staff with trait profiles, expansion events (company, day, branch), supplier lead times. Tests: same seed same `plan_hash`; different seed differs; every plan respects tier limits; every company has at least one expiry vertical or an explicit reason; expansion never exceeds the branch cap; no accusation wording in generated text.
- [x] **Task 4: Behavior.** `make_individuals` (persistent ids, home branch, wallet, visit frequency, mission affinity), `day_visits` (hourly demand curve per vertical, mission-driven baskets, price response through the hidden elasticity applied to the price ratio, small bounded noise). Tests: deterministic per seed and day; same individual keeps home branch across days; a discount raises expected units (monotonic on average); high-elasticity archetypes respond more than low; evening vs morning mission mix differs; elasticity is not importable outside `behavior` (grep test).
- [x] **Task 5: PesoWebDriver.** Port the onboarding chain and the shift, sale, return, receiving and read calls from the PowerShell smokes. Retries only on connection errors; tier-limit refusals become `DriverRefusal` results, not crashes; every call tags `X-Sim-Run`; tokens never logged. Tests (mock server via `unittest.mock`/a tiny local `http.server`): request shapes match the contract (multipart for category, brand, product, purchase, sale; JSON for the rest), refusal handling, no token in log output.
- [x] **Task 6: Onboard the world.** `runner build`: register each owner, root raises tier to Business, add branches, staff users (own logins), tax/unit/category/brand/supplier, catalog (expiry products with staggered batches through purchase receipts), opening stock. Idempotent state file (`runs/<run>/world.json`) mapping plan ids to PesoWeb ids. Live check on the throwaway DB with the `smoke` profile.
- [x] **Task 7: Day run and expansion.** `runner day`: virtual clock for one business day; staff open shifts, shoppers buy through `AddSale` (FEFO and markdown pricing are PesoWeb's), some returns, stock top-up purchases by lead time, shifts closed with actual cash, a new branch opened mid-run (company, branch, staff, assortment, opening stock) and visited the same day. Writes the action log and its SHA-256. Live check: the same seed twice gives the same hash.
- [x] **Task 8: Incidents, ledger, scoring.** Incident types: `CASH_SHORT` (staff closes under the expected amount), `NEAR_EXPIRY_BATCH` (short-dated delivery), `UNREPORTED_SHORT_DELIVERY` (no receiving report, so PesoWeb stays silent), `HIDDEN_SHRINK` (stock leaves without a sale and no count). `score` matches each injected incident to a PesoWeb exception (same branch, mapped type, raised after injection) for **caught**, else to an AI finding for **ai_found**, else **undetected**. Golden test: 5 known incidents, scripted exceptions and findings, exact split asserted. Live check: the day run catches the cash and expiry incidents and leaves the other two undetected (Plan 5 closes that gap).
- [x] **Task 9: Package.** `sim/README.md` (run recipe against the LocalDB environment in `pesoweb-additions/README.md`), update spec implementation notes and this plan's execution log, `.gitignore` `sim/runs/`, commit with explicit paths.

## Exit criteria

- All unit tests pass (`python -m unittest discover -s sim/tests`).
- On the throwaway PesoWeb database, `build` creates a 5-company group and `day` runs a seeded day with sales, shifts, a mid-run branch opening and recorded ground truth.
- The scorecard for that day reports caught, AI-found (zero for now) and undetected per incident, from real exception data.
- Same seed, same action-log hash.

## Not in this plan

LLM-generated archetypes and business plans (Plan 5 plugs into the same schemas), the markdown optimizer and prediction recorder (Plan 5), three-way runs, Quick Sim lane, UI (Plan 6).

## Execution log and corrections

- Built 2026-10-05 in `sim/`; 58 unit tests pass (`python -m unittest discover -s tests -t .`, no pytest available).
- Live on the throwaway PesoWeb database: `smoke` and `starter` worlds built through the real API (5 tenants raised to Business by the root login), a seeded day ran with 0 failed sales (111 smoke, 461 starter), two branches opened mid-run and traded the same day, 5 incidents injected and scored from real exception data. Same seed gave the identical action-log hash on two fresh builds; a different seed differed.
- Result of the first scored day (smoke, seed 21): 3 caught (2 cash shortages, 1 near-expiry batch), 0 AI-found, 2 undetected (`UNREPORTED_SHORT_DELIVERY`, `HIDDEN_SHRINK`) plus 2 unrelated exceptions (counting noise). Plan 5 targets the two undetected.
- PesoWeb findings that shaped the sim (added to `Docs/onboarding-contract.md`): `AddWarehouse` does not assign the owner to the new branch (the owner then cannot stock it or list its exceptions until `UpdateUser` adds it); usernames are unique across all tenants; `Exceptions/List` is limited to the caller's branches; `Exceptions/Detect` must be triggered (the sim calls it as the nightly job); FEFO sells a short-dated batch through during trading, so a late delivery must land after close to be alertable.
- Corrections to the plan: the near-expiry incident moved to after trading; cash incidents match within a 10 peso tolerance because the sim adds up to 5 pesos of counting noise to every shift; expiry incidents match on the exact batch reference so baseline alerts cannot explain them. Staff all use the owner's role (the roles endpoint is closed to new owners). One cashier per branch sells (a shift is per branch).
- Not done here (by design): LLM-written archetypes and plans, the markdown hook (`price_ratio` is wired in `behavior.day_visits` but the runner passes none until Plan 5), per-shopper PesoWeb customers, virtual time.

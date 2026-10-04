# PesoWeb additions for Sim.PesoWeb

PesoWeb (the system under test) is a separate product repository. This folder carries only the **additive** changes made for the hackathon, so the work is visible and reproducible. The work lives on branch `Retail_MissionCommerceAI` of the PesoWeb repo.

## What the patches add

**Plan 1 (`patches/plan1`, 7 commits)**
- xUnit test project `Retailo.Tests` on an in-memory `AppDBContext`
- Business event outbox (`BusinessEvent`) tagged with the `X-Sim-Run` header
- Cashier shift and cash drawer (`CashShift`, `CashMovement`), expected cash and variance
- Nullable `ShiftId / CashierId / PosTerminal` on `Sale`; audit context columns on `AuditLog`
- Inventory ledger vs on-hand drift service
- Read-only `/api/ai/events`, `/api/ai/cash-shifts`, `/api/ai/ledger-drift`

**Plan 2 (`patches/plan2`, 7 commits)**
- Per-tenant pricing policy and guardrails (`/api/Pricing/*`), enforced inside PesoWeb
- Price-change ledger and per-batch markdowns applied at the POS in `AddSale`
- `PriceChanged` events
- Expiry risk report and expired-stock write-off (`/api/Expiry/*`)
- Read endpoints `/api/ai/expiry-risk`, `/api/ai/price-changes`, `/api/ai/active-markdowns`
- Idempotent deployment script `scripts/20261004_sim_foundation_and_markdown_core.sql` (included in the last Plan 2 patch)

69 unit tests in total.

## Apply

    git checkout -b Retail_MissionCommerceAI
    git am pesoweb-additions/patches/plan1/*.patch
    git am pesoweb-additions/patches/plan2/*.patch
    dotnet test Retailo.Tests/Retailo.Tests.csproj
    dotnet ef database update            # local/dev database only
    # production: run the idempotent script in scripts/ instead

Note: the migrations deliberately omit EF's scaffolded `UpdateData` statements for seed rows (the model's seed data uses `DateTime.UtcNow`, so EF would otherwise rewrite seed rows on every database).

## Smoke scripts (`smoke/`)

Status: **written and syntax-checked, not yet run against a live app.** They need PesoWeb running on http://localhost:5061 with SQL Server up and the migrations applied.

| Script | What it proves |
|---|---|
| `onboarding-contract.ps1` | Register, branch creation, and lists the API routes the simulator driver needs |
| `cash-shift-smoke.ps1` | Open shift, cash movement, close with variance, events and read APIs |
| `pricing-smoke.ps1 -Yes` | Guardrails, a markdown applied to a real sale, events, ledger. DEV tenant only (creates two real sales). Credentials come from `PESOWEB_EMAIL` / `PESOWEB_PASSWORD`. |

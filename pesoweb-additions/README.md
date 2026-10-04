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

Status: **all pass against a live app on a restored dev-database copy (2026-10-05).** They need PesoWeb running with the migrations applied (default URL `http://localhost:5061`; pass `-BaseUrl` otherwise).

| Script | What it proves |
|---|---|
| `onboarding-contract.ps1` | Register, tier-limited branch creation, and lists the API routes the simulator driver needs |
| `seed-expiry-tenant.ps1` | Dot-source for `New-ExpiryTenant`: the owner's setup chain (category, brand, unit, tax, supplier, expiry product, purchase with a batch). Documented in `Docs/onboarding-contract.md` |
| `cash-shift-smoke.ps1` | Open shift, second shift refused, cash movement, close with variance, events and read APIs |
| `pricing-smoke.ps1 -Email -Password -Yes` | Guardrails refuse an absurd markdown, a markdown prices a real sale (100 down to 80, back to 100 after it ends), events, ledger, expiry risk. DEV tenant only (creates two real sales). Credentials come from parameters or `PESOWEB_EMAIL` / `PESOWEB_PASSWORD`. |

| `plan3-smoke.ps1` | Batch cost stored, cash refund on a sale return, cash-variance and expiry exceptions (idempotent), stock count approval through FEFO with zero ledger drift, short-delivery receiving report, all events, and `Group/Overview` returning 403 to a tenant owner |

Also verified live as the root `SuperAdmin` (user 1) on the restored database: `GET /api/Group/Overview` returned 22 companies and 24 branches with roll-up totals. To repeat it, set user 1's password in the throwaway database only (password hash = lowercase hex MD5 of the UTF-8 password), log in at `/api/Auth/Login`, and call the endpoint.

## Plan 3 additions

- `scripts/20261005_widen_users_subscription_check.sql`: widens the stale signup constraint (idempotent).
- `scripts/20261005_plan3_features.sql`: idempotent SQL for the five Plan 3 migrations (constraint, exception records, stock counts, receiving reports, exception permission grants) for databases that do not run `dotnet ef database update`.
- Patches: `patches/plan3` (8 patches, tag `plan3-complete`).
- New APIs: `Exceptions/*`, `StockCounts/*`, `Receiving/*`, `Group/Overview` (root `SuperAdmin` only), `/api/ai/exceptions`, `/api/ai/receiving-reports`.

## Live verification environment (no admin rights needed)

PesoWeb databases come from a backup plus SQL scripts, not from running every EF migration (an old migration has a foreign-key cycle, and the history is incomplete). To get a throwaway database on SQL Server LocalDB:

    # 1. start LocalDB and restore the repo's backup as a new database
    SqlLocalDB start MSSQLLocalDB
    sqlcmd -S "(localdb)\MSSQLLocalDB" -E -C -Q "RESTORE DATABASE PesoWeb_MissionDev FROM DISK=N'<repo>\DATABASE\PesoWebFullbackup_JUNE302026_v1' WITH MOVE 'heavycoder-Retail2' TO N'<dir>\PesoWeb_MissionDev.mdf', MOVE 'heavycoder-Retail2_log' TO N'<dir>\PesoWeb_MissionDev_log.ldf', REPLACE"
    # 2. record the two migrations whose objects the backup already has, then apply the pending ones (including ours)
    sqlcmd -S "(localdb)\MSSQLLocalDB" -E -C -d PesoWeb_MissionDev -Q "INSERT INTO __EFMigrationsHistory VALUES (N'20260511235517_AddChatMessaging',N'7.0.13'),(N'20260514_AddOfflinePinToUsers',N'7.0.13')"
    $env:ConnectionStrings__default = 'Server=(localdb)\MSSQLLocalDB;Database=PesoWeb_MissionDev;Trusted_Connection=True;TrustServerCertificate=True;MultipleActiveResultSets=true'
    dotnet ef database update --project Retailo.csproj --no-build
    # 3. not needed any more: the WidenUsersSubscriptionCheck migration (applied in step 2) does this. Only for a database that skipped it (see Docs/onboarding-contract.md, finding 2):
    sqlcmd -S "(localdb)\MSSQLLocalDB" -E -C -d PesoWeb_MissionDev -Q "ALTER TABLE Users DROP CONSTRAINT CK_Users_Subscription_Valid; ALTER TABLE Users ADD CONSTRAINT CK_Users_Subscription_Valid CHECK (Subscription IN (1,2,3,4,5))"
    # 4. run the app against it (same environment variable), then run the smoke scripts
    dotnet run --project Retailo.csproj --no-build --no-launch-profile --urls http://localhost:5071

Verified on that database: all six new tables and the new columns exist, all 9 owner roles received the 7 new permissions, the tier limits are 5 / 2 / 1 branches, and user 1's `LastLogin` was untouched.

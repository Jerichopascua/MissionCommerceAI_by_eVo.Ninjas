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

## Plan 5 additions (read-only AI feeds)

`patches/plan5` (3 patches, tag `plan5-complete`) adds to `AiController`, all `AI.Read`, no new tables and no migration:
- `GET /api/ai/receipts?warehouseId=&afterId=&take=` stock received through purchases (`PURCHASE_IN` ledger rows) with `hasReceivingReport`.
- `GET /api/ai/movements?warehouseId=&type=SALE_OUT&afterId=&take=` inventory ledger rows (what moved, when, from which batch).
- `GET /api/ai/batches?warehouseId=` every batch with stock on hand (the expiry feed lists only the alert window).

## Plan 7 addition (guarded list-price changes)

`patches/plan7` (tag `plan7-complete`): `POST /api/Pricing/ListPrice`, `ApproveListPrice`, `RejectListPrice` and `GET ListPriceChanges` with `ListPriceGuardrails` and `ListPriceService`; no new tables and no migration (the price ledger row with no batch is a list-price change). A list-price change always needs a human approval. Existing `MarkdownService` approval now ignores rows without a batch.

## Plan 8 addition (Approval Center)

`patches/plan8` (2 patches, tag `plan8-complete`):
- Back end: one migration `AddApprovalCenter` (new `PricingPolicy` settings and `PriceChange` evidence columns) and `GrantApprovalLanePermissions` (SQL grant to SuperAdmin roles; script in `scripts/20261005_approval_center.sql`). New permissions `Pricing.Approve.Store`, `.Pricing`, `.Owner`. Endpoints: `GET /api/Pricing/Approvals?lane=&type=`, `POST ApproveBulk`, `POST UndoListPrice`; `ApproveListPrice` accepts `NewPrice`. Lanes by size and evidence; auto-approve is off by default; no self-approval unless the tenant has one user; proposals expire.
- Angular screen at `/pricing/approvals` (menu entry under Inventory, needs `Pricing.View`): queue by lane, evidence and rule checks, approve, reject, approve at an edited price, bulk approve low-risk, undo, owner settings, keys j/k/a/r.
- Checked by 171 PesoWeb tests, `sim/scripts/approval_center_check.py` (17 live checks, including the simulated approver) and an Angular template compile (`ngc`). The screen has not been clicked through in a browser (screenshot tooling timed out).

Simulation side: `sim/simpeso/approver.py` is a seeded virtual store manager that works the same queue through the normal endpoints (so the audit log, rules and undo apply). Its choices are an assumption about people, not a measurement.

## Plan 9 addition (AI Control: on/off and run now)

`patches/plan9` (2 patches, tag `plan9-complete`):
- Tables `AiFeatureSettings` (one row per company and feature; no row means ON, so existing companies keep working) and `AiRunRequests`, migration `AddAiControl`, permission `AI.Control` (granted to SuperAdmin roles by `GrantAiControlPermission`; script `scripts/20261005_ai_control.sql`).
- Owner endpoints (`AI.Control`): `GET /api/ai/control`, `PUT /api/ai/control/{feature}` (`{"enabled":false}`), `POST /api/ai/control/run/{feature}`. Agent endpoints (`AI.Read`): `GET /api/ai/settings`, `GET /api/ai/run-requests?status=Requested`, `POST /api/ai/run-requests/{id}/start`, `POST .../finish`.
- Enforcement is in PesoWeb: with AI Pricing off, an AI list-price proposal or markdown is refused (422 `AI_FEATURE_OFF`); a person's own proposals are not affected. Switching a feature off cancels a run nobody started.
- Angular screen at `/ai/control` (menu "AI Control"): six cards with the switch, build state, Run now, and the last run's result.
- Only AI Pricing can be run now. The other five show their switch and build state; Monitoring and Insight are partly built, Replenish and Customer Mission are not built, Loss Prevention runs inside simulations only.

Agent side: `sim/simpeso/agent_service.py` (`python -m simpeso.agent_service --run real2 --company c1 --once`, or `--interval 30` to keep polling) reads the switches, picks up run requests and runs the AI Pricing handler, which puts the best list-price changes into the Approval Center (skipping products that already have one waiting). Checked by 178 PesoWeb tests and `sim/scripts/ai_control_check.py` (16 live checks).

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

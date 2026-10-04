# Plan 3: Remaining PesoWeb Features Implementation Plan (compact)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development. Steps use checkbox syntax.
>
> **Format note:** unlike Plans 1 and 2, this plan specifies interfaces, behaviors, and the test cases to write instead of pasting full code, because the code is written once during execution. The exact signatures below are binding; the tests listed are the minimum. Every task ends with a build, the full test suite, and a commit.

**Goal:** Finish the PesoWeb capabilities the simulator needs: working signup on any database, real batch costs, sale-return cash refunds and events, an Exception Center (the "system caught" column), stock counts, receiving discrepancies, and a read-only group roll-up for the central company.

**Architecture:** Same as Plans 1 and 2: additive tables, small services tested on the in-memory context, thin controllers, events through `IBusinessEventPublisher`. The group roll-up reuses the existing root-`SuperAdmin` cross-tenant pattern (`IgnoreQueryFilters` under the root-only `Subscription.Tenants` policy), so it needs no new tables.

**Tech Stack:** ASP.NET Core (net9.0), EF Core 7.0.13, SQL Server, xUnit + EF InMemory, PowerShell smoke.

**Spec:** `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md` (section 4 items 2, 4, 6, 7, 9; "Corporate group").

## Plan series

| Plan | Scope | Status |
|---|---|---|
| 1 | Cash shift, event outbox, ledger drift, read API | done, verified live |
| 2 | Expiry risk, guardrails, price ledger, POS markdowns | done, verified live |
| **3 (this)** | Signup constraint fix, batch cost, sale-return refunds and events, Exception Center, stock count, receiving discrepancy, group roll-up | execute now |
| 4 | Sim core | next |
| 5 | AI on AMD | after |
| 6 | Proof, Quick Sim lane, UI, packaging | after |

## Global Constraints

- Everything from Plans 1 and 2 applies: additive only (the two approved exceptions are Tasks 1 and 2), `TenantID` on tenant tables, PesoWeb controller conventions, permissions in `Helpers/Permissions.cs`, branch `Retail_MissionCommerceAI` in the worktree `D:\git\Retailo_v1_mission`, explicit `git add` paths only.
- **Migrations:** after `dotnet ef migrations add ... --no-build`, always run `python pesoweb-additions/tools/strip_seed_noise.py <migration.cs>` and verify only the intended objects remain. Do not hand-edit snapshots.
- Owner-role permissions for new features are granted to every tenant's `SuperAdmin` role by an idempotent SQL migration (same pattern as `GrantPricingPermissionsToOwnerRoles`).
- In-memory tests enforce `[Required]`: give test entities their required strings.
- The group roll-up is **read-only**, root-`SuperAdmin` only, and never writes.
- Exception Center rules are intentionally **basic** (they are the "system caught" column): cash variance on shift close, expired stock still in stock, expiry alert, negative stock, low stock, supplier short shipment, stock-count variance. Pattern-level anomalies are the AI's job.
- No secrets in git; wording "variance"/"discrepancy", never accusations.
- Live verification uses the throwaway LocalDB database `PesoWeb_MissionDev` (recipe in `pesoweb-additions/README.md`).

---

## Task 1: Signup constraint fix (approved change)

**Files:** `Migrations/<ts>_WidenUsersSubscriptionCheck.cs` (+ Designer, snapshot unchanged except metadata), `scripts/20261005_widen_users_subscription_check.sql`.

**Behavior:** a guarded script and an EF migration that, when `CK_Users_Subscription_Valid` exists and does not already allow `4` and `5`, drops it and re-adds `CHECK (Subscription IN (1,2,3,4,5))`. When the constraint is missing or already widened it does nothing. Both use the same SQL; the migration's `Down` restores `IN (1,2,3)` only if no row uses 4 or 5.

- [ ] Write the SQL with an `IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_Users_Subscription_Valid' AND definition NOT LIKE '%(5)%')` guard.
- [ ] Generate the migration (`ef migrations add WidenUsersSubscriptionCheck --no-build`), strip seed noise, replace the body with `migrationBuilder.Sql(...)` using the guarded SQL.
- [ ] **Verify live:** on `PesoWeb_MissionDev` first set the constraint back to `IN (1,2,3)`, run the script, then run it again (idempotent), then confirm a `Register` call succeeds (`New-SimTenant`).
- [ ] Commit.

## Task 2: Store purchase unit cost on batches (approved change)

**Files:** `Controllers/PurchasesController.cs` (existing `ApplyStockDeltaAsync` and its AddPurchase/UpdatePurchase call sites), `Retailo.Tests/InventoryBatchCostTests.cs`.

**Behavior:** `ApplyStockDeltaAsync` gains an optional `decimal? unitCost = null` parameter and passes it to `BatchReceiveInput.UnitCost` instead of the hard-coded `null`. The purchase paths (add, and update when stock increases) pass `detail.UnitCost` for batch receives. All other callers (returns, adjustments, transfers) are unchanged (`null`). Existing batches stay `NULL` and keep the product-cost fallback.

**Tests (service level, `InventoryBatchService.ReceiveAsync`):**
- receiving with `UnitCost = 42` sets `ProductBatch.Cost = 42` and the ledger row `UnitCost = 42`;
- receiving into an existing batch with `UnitCost = null` keeps the old cost (`batch.Cost = input.UnitCost ?? batch.Cost`);
- receiving into an existing batch with a new cost updates it.

- [ ] Write the tests, then make the controller change, then build and run the suite.
- [ ] **Verify live:** seed with `New-ExpiryTenant` and confirm `NearExpiryBatches` shows `cost = 60` and the ledger `PURCHASE_IN` row has `UnitCost = 60` (check via SQL).
- [ ] Commit.

## Task 3: Sale-return cash refunds and sale events (item 2)

**Files:** `Services/BusinessEventPublisher.cs` (add `SaleReturned`, `SaleDeleted` constants), `Services/CashShiftService.cs` (new method), `Controllers/SalesController.cs` (hooks in `AddReturn` and the sale-delete action), `Retailo.Tests/CashRefundTests.cs`.

**Interfaces:**
- `ICashShiftService.RecordCashRefundAsync(int warehouseId, int cashierId, string originalPaymentMethod, decimal amount, string referenceNo, DateTime now)` returns `CashMovement` or `null`. It records a `Refund` movement on the cashier's **open** shift in that warehouse when the original sale was paid in cash (case-insensitive `"Cash"`) and `amount > 0`; otherwise returns `null` without error.
- `AddReturn` (after totals are final, before `scope.Complete()`): look up the original sale's `PaymentMethod`, call `RecordCashRefundAsync(..., $"sr-{newSaleReturn.Id}", now)`, publish `SaleReturned` `{ saleReturnId, saleId, totalAmount, paymentMethod, shiftId?, refundRecorded }`, and save.
- The sale-delete action publishes `SaleDeleted` `{ saleId, totalAmount, paymentMethod }` (read the sale before it is removed).

**Tests:** cash sale + open shift records a Refund movement and the shift's expected cash drops by the amount; non-cash original payment records nothing; no open shift records nothing; zero amount records nothing; the movement carries the reference `sr-<id>`.

- [ ] Tests first, then the service method, then the two controller hooks (read the surrounding code before editing; anchors are the existing `scope.Complete()` calls inside `AddReturn` and the delete-sale action).
- [ ] **Verify live:** open a shift, make a cash sale, return it through `api/Sales/AddReturn`, confirm a `Refund` movement and a `SaleReturned` event.
- [ ] Commit.

## Task 4: Exception Center (item 7)

**Files:** `Models/ExceptionRecord.cs`, `Services/ExceptionService.cs`, `Controllers/ExceptionsController.cs`, `Helpers/Permissions.cs` (`Exceptions.View`, `Exceptions.Manage`), `Controllers/AiController.cs` (`/api/ai/exceptions`), `Services/CashShiftService.cs` (record on close), migrations `AddExceptionRecords` and `GrantExceptionPermissionsToOwnerRoles`, tests `ExceptionServiceTests.cs`.

**Model `ExceptionRecord`:** `long Id, int TenantID, int? WarehouseId, string Type (40), string Severity (Low|Medium|High), string Status (Open|Resolved), string Source ("System"), DateTime DetectedAt, string ReferenceNo (100), string Description (500), string EvidenceJson, DateTime? ResolvedAt, int? ResolvedBy, string ResolutionNote (300)`. Index `(TenantID, Status, DetectedAt)`.

**Constants:** `ExceptionTypes`: `CASH_VARIANCE, EXPIRED_STOCK, EXPIRY_ALERT, NEGATIVE_STOCK, LOW_STOCK, SUPPLIER_SHORT_SHIPMENT, STOCK_COUNT_VARIANCE`; `ExceptionSeverity`; `ExceptionStatus`.

**Interfaces (`IExceptionService`):**
- `Task<bool> RecordAsync(string type, string severity, int? warehouseId, string referenceNo, string description, object evidence, DateTime now)` adds an Open exception **unless an Open one with the same `Type` + `ReferenceNo` exists** (idempotent); returns `true` when added. It does not save; the caller saves (so it commits with the business change), except where noted.
- `Task<int> DetectAsync(IReadOnlyCollection<int> warehouseIds, DateTime now)` runs the stock rules and saves; returns the number of new exceptions:
  - `EXPIRED_STOCK` (High): expiry-tracked batch with `QtyOnHand > 0` and expiry before today; reference `batch-<id>`; evidence qty, cost, pesos.
  - `EXPIRY_ALERT` (Low, Medium when <= 2 days): batch inside its product's `ExpiryAlertDays`; reference `batch-<id>`.
  - `NEGATIVE_STOCK` (High): `ProductWarehouse.Quantity < 0`; reference `pw-<warehouse>-<product>`.
  - `LOW_STOCK` (Medium): `Quantity <= Product.StockAlert` and `StockAlert > 0` and `Quantity >= 0`; reference `pw-<warehouse>-<product>`.
- `Task<ExceptionRecord> ResolveAsync(long id, int userId, string note, DateTime now)`; throws `InvalidOperationException` if missing or already resolved.
- `Task<List<ExceptionRecord>> ListAsync(int? warehouseId, string status, string type, int take)`.
- `CashShiftService.CloseAsync` records `CASH_VARIANCE` when `Variance != 0` (severity High when `|variance| >= 1000`, else Medium; reference `shift-<id>`; description "Unexplained cash variance of <amount> on shift <id>").

**Endpoints:** `GET api/Exceptions/List?warehouseId=&status=&type=` (`Exceptions.View`); `POST api/Exceptions/Detect?warehouseId=` (`Exceptions.Manage`, limited to the caller's branches); `POST api/Exceptions/Resolve` body `{ id, note }` (`Exceptions.Manage`); `GET ~/api/ai/exceptions?afterId=&take=` (`AI.Read`, cursor like events).

**Tests:** idempotent record (second identical record returns false, one row); each detection rule fires and respects branch filter and tenant isolation; a resolved exception does not block a new one with the same reference; resolve twice throws; cash close with variance -1500 records one High exception, zero variance records none; severity thresholds.

- [ ] Tests first, then model, service, wiring, controller; migrations with seed noise stripped; build, full suite.
- [ ] **Verify live:** close a shift with a variance and see the exception; run Detect on a tenant with an expired batch and see `EXPIRED_STOCK`; resolve one; `/api/ai/exceptions` returns them.
- [ ] Commit.

## Task 5: Stock count with variance (item 4)

**Files:** `Models/StockCount.cs` (`StockCount`, `StockCountLine`), `Services/StockCountService.cs`, `Controllers/StockCountsController.cs`, migration `AddStockCounts`, tests `StockCountServiceTests.cs`.

**Models:** `StockCount { int Id, int TenantID, int WarehouseId, string Status (Open|Approved|Cancelled), string Note, int CreatedBy, DateTime CreatedAt, int? ApprovedBy, DateTime? ApprovedAt }`; `StockCountLine { long Id, int TenantID, int StockCountId, int ProductId, int? VariantId, decimal SystemQty, decimal? CountedQty, decimal? Variance, string Reason }`.

**Interfaces (`IStockCountService`):**
- `Task<StockCount> CreateAsync(int warehouseId, IReadOnlyCollection<int> productIds, int userId, string note, DateTime now)`: snapshots `SystemQty` from `ProductWarehouse.Quantity` (0 when no row) for each product (all products with a row in that warehouse when `productIds` is empty).
- `Task SubmitCountsAsync(int stockCountId, IReadOnlyList<(int ProductId, decimal CountedQty, string Reason)> counts)`: only on an Open count; sets `CountedQty` and `Variance = CountedQty - SystemQty`; rejects negative counts and unknown products.
- `Task<StockCountApproval> ApproveAsync(int stockCountId, int approverId, DateTime now)`: for every line with non-zero variance posts the adjustment through the ledger: `TransactionType = "STOCK_COUNT_ADJ"`, `QtyIn`/`QtyOut` = |variance|, `UnitCost` from batch/product; non-expiry products update `ProductWarehouse.Quantity`; expiry-tracked products **consume FEFO** for negative variance (via `IInventoryBatchService.ConsumeFefoAsync` with `TransactionType = "STOCK_COUNT_ADJ"`); a **positive variance on an expiry-tracked product is rejected** with a message to use a stock adjustment with a batch (the whole approval fails, nothing posts). Records a `STOCK_COUNT_VARIANCE` exception (reference `count-<id>-<product>`, severity High when the variance value >= 1,000) and publishes event `StockCountApproved`. Returns `{ lines, unitsAdjusted, pesosLost, pesosGained }`.
- Status moves Open to Approved; approving twice throws.

**Endpoints (`StockCountsController`, `[Authorize(Policy="Inventory.StockAdjustmentAdd")]`):** `POST Create`, `POST Submit`, `POST Approve`, `GET Detail?id=`, `GET List?warehouseId=`. Branch access checked via `UserWarehouses`.

**Tests:** create snapshots system quantities; submit computes variance; approving a -8 variance on a non-expiry product lowers the quantity by 8 and writes a `STOCK_COUNT_ADJ` ledger row with `QtyOut = 8`; an expiry product consumes FEFO (earliest batch first); a positive variance on an expiry product is rejected and posts nothing; approve twice throws; exception recorded with the right severity; the Plan 1 drift check shows no drift after approval for a product whose ledger and cache were consistent.

- [ ] Tests first, then models, service, controller, migration; build, full suite.
- [ ] **Verify live:** seed an expiry product (20 units), count 18 through the API, approve, confirm batch quantity 18, ledger row, exception, and `ledger-drift` still empty.
- [ ] Commit.

## Task 6: Receiving discrepancy (item 6)

**Files:** `Models/ReceivingReport.cs`, `Services/ReceivingService.cs`, `Controllers/ReceivingController.cs`, migration `AddReceivingReports`, tests `ReceivingServiceTests.cs`.

**Model `ReceivingReport`:** `long Id, int TenantID, int WarehouseId, string SourceType (Purchase|Transfer), int SourceId, int ProductId, decimal ExpectedQty, decimal ReceivedQty, decimal Difference (Received - Expected), string Status (Matched|Short|Over), string Note, int ReportedBy, DateTime ReportedAt`.

**Interface (`IReceivingService`):** `Task<ReceivingReport> ReportAsync(int warehouseId, string sourceType, int sourceId, int productId, decimal expectedQty, decimal receivedQty, string note, int userId, DateTime now)`. Validation: source type in {Purchase, Transfer}; quantities >= 0; for `Purchase` the purchase must exist in this tenant and belong to the warehouse. The stock itself is already correct (it was entered at the received quantity); this records what was **expected**. `Short` records a `SUPPLIER_SHORT_SHIPMENT` exception (High when the missing value >= 1,000, else Medium; reference `recv-<sourceType>-<sourceId>-<product>`) using the product cost; `Over` records a Low exception of the same type; `Matched` records none. Publishes event `ReceivingReported`.

**Endpoint:** `POST api/Receiving/Report` (`[Authorize(Policy="Purchases.PurchaseAdd")]`) and `GET api/Receiving/List?warehouseId=&status=`; `GET ~/api/ai/receiving-reports` (`AI.Read`).

**Tests:** short, over and matched classification; exception only for short/over; the purchase must belong to the tenant and warehouse (another tenant's purchase id is rejected); negative quantities rejected; transfer reports skip the purchase lookup.

- [ ] Tests first, then model, service, controller, migration; build, full suite.
- [ ] **Verify live:** report a purchase receipt of 93 against an expected 100 and see the report, a `SUPPLIER_SHORT_SHIPMENT` exception and the event.
- [ ] Commit.

## Task 7: Group roll-up for the central company (item 9)

**Files:** `Services/GroupOverviewService.cs`, `Controllers/GroupController.cs`, tests `GroupOverviewServiceTests.cs`.

**Behavior:** root-`SuperAdmin` only (`[Authorize(Policy = "Subscription.Tenants")]` plus an explicit `IsRootSuperAdmin(await GetCurrentUserRecordAsync())` check returning 403 otherwise). Read-only. Uses `IgnoreQueryFilters()` and groups by `TenantID`; never writes.

**Interface (`IGroupOverviewService`):** `Task<GroupOverview> GetAsync(DateTime now)` returning:
- `GroupOverview { DateTime GeneratedAt; GroupTotals Totals; List<TenantOverview> Tenants }`
- `TenantOverview { int TenantId; string CompanyName; int Subscription; int BranchCount; GroupTotals Totals; List<BranchOverview> Branches }`
- `BranchOverview { int WarehouseId; string Name; decimal SalesToday; int TransactionsToday; int OpenShifts; decimal CashVarianceToday; decimal ExpiryAtRiskPesos; decimal ExpiredUnwrittenPesos; decimal WrittenOffPesos; int ActiveMarkdowns; int OpenExceptions }`
- `GroupTotals` with the same numeric fields summed (sales, transactions, open shifts, cash variance, at risk, expired unwritten, written off, active markdowns, open exceptions, branches).
- "Today" is `now.Date` in the stored local frame. Expiry risk uses the same rules as `ExpiryService` (status by days left and `ExpiryAlertDays`, cost fallback to product cost). Cash variance today sums `Variance` of shifts closed today. Tenant names come from `AppSettings.CompanyName`; subscription from the tenant's effective owner (lowest-Id user, as elsewhere).

**Endpoint:** `GET api/Group/Overview` (also `GET ~/api/ai/group-overview` is **not** exposed; the AI uses per-tenant APIs).

**Tests:** two tenants with two branches each aggregate correctly (sales, expiry at risk, written off, open exceptions, markdowns, open shifts); tenants and branches with no activity still appear with zeros; a branch's numbers never leak into another tenant's totals; totals equal the sum of tenants; the service does not modify data (counts of rows unchanged after the call).

- [ ] Tests first, then the service and controller; build, full suite.
- [ ] **Verify live:** log in as the root `SuperAdmin` of the throwaway database (the restored user 1; its password is not in the repo, so use a tenant owner to confirm a **403** and use SQL to confirm the numbers, and ask the owner to run the root call themselves) and confirm that a normal tenant owner gets 403.
- [ ] Commit.

## Task 8: Ship Plan 3

- [ ] Smoke: extend `pesoweb-additions/smoke` with `plan3-smoke.ps1` covering tasks 3 to 6 through the real API (refund recorded, exception on cash close, expiry detect, stock count approve, receiving report). Run it and keep it passing.
- [ ] `dotnet ef migrations script --idempotent` to `scripts/20261005_plan3_features.sql`; confirm the new migrations are guarded.
- [ ] Export patches since the last export tag (`git tag plan2-complete` before starting, then `git format-patch plan2-complete..HEAD` into `pesoweb-additions/patches/plan3`); scan for secrets.
- [ ] Update `Docs/onboarding-contract.md` findings (fixed items), `pesoweb-additions/README.md`, the spec implementation notes, and this plan's execution log. Commit in the hackathon repo.

## Exit criteria

- A tenant can sign up on a database built from the repo's scripts; purchase costs land on batches.
- A cash sale return records a cash refund on the open shift and emits `SaleReturned`; deleting a sale emits `SaleDeleted`.
- The Exception Center lists cash variances, expired stock, expiry alerts, negative and low stock, short shipments and stock-count variances, each idempotent and resolvable, and readable by the AI.
- A stock count can be created, submitted and approved, posting the adjustment through the ledger and FEFO.
- A receiving report records expected versus received.
- The root `SuperAdmin` gets a read-only company-to-branch overview; tenant owners get 403.
- All unit tests and `plan3-smoke.ps1` pass.

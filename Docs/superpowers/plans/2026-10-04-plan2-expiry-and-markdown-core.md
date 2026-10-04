# Plan 2: Expiry Risk and Agentic Markdown Core (PesoWeb) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give PesoWeb everything the markdown-pricing AI needs to act safely: expiry money-at-risk and a real expired-stock write-off, per-tenant pricing guardrails, a price-change ledger, per-batch markdowns applied at the POS, and `PriceChanged` events for channel sync.

**Architecture:** All additive, in the existing ASP.NET Core 9 / EF Core 7 / SQL Server app. New pure logic (`MarkdownGuardrails`) sits under small services (`MarkdownService`, `MarkdownPricingService`, `ExpiryService`) with xUnit tests on the in-memory test context from Plan 1. Controllers are thin. The sale path gets one hook: after FEFO consumption has chosen the batches, each batch's units are priced at its active markdown (if the guardrails still hold), and the line gets the quantity-weighted price. Guardrails live **inside PesoWeb** and cannot be overridden by the caller.

**Tech Stack:** ASP.NET Core (net9.0), EF Core 7.0.13, SQL Server, xUnit + EF InMemory, PowerShell + curl.exe (smoke).

**Spec:** `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md` (sections "Agentic markdown pricing", "Expiry-tracked catalog and FEFO monitoring", section 4 items 5, 10, 11, 12, 13).

**Depends on Plan 1 being complete** (`docs/superpowers/plans/2026-10-03-plan1-p0-and-pesoweb-foundation.md`): it uses `IBusinessEventPublisher`, `BusinessEventTypes`, `TestAppDbContext`, `AiController`, `ILedgerService`, the `AI.Read` permission and the `SalesController` constructor with `IBusinessEventPublisher`.

## Plan series

| Plan | Scope | Status |
|---|---|---|
| 1 | P0 AMD smoke; cash shift, event outbox + read API, ledger drift | written |
| **2 (this)** | Expiry risk + write-off; pricing policy and guardrails; price ledger; markdowns at the POS; `PriceChanged` events | write now |
| 3 | Corporate group link + roll-up (item 9), Enterprise tier row, Exception Center (7), stock count (4), receiving discrepancy (6), sale lifecycle events (2) | after plan 2 |
| 4 | Sim core: corporate world, owners, verticals, behavior with hidden price response, driver, incident scoring | after plan 3 |
| 5 | AI on AMD: demand-response model, markdown optimizer, prediction recorder, mission signals, investigator | after plan 4 |
| 6 | Proof (three-way runs, calibration), Quick Sim lane, UI, packaging, demo | after plan 5 |

## Execution log and corrections (2026-10-05)

Executed inline in the worktree `D:\git\Retailo_v1_mission` (branch `Retail_MissionCommerceAI`), right after Plan 1. Tasks 1 to 7 are done with **69 tests passing** (Plan 1's 23 plus 46). Task 8 (`pricing-smoke.ps1`) is written and syntax-checked but **not run** because SQL Server was stopped; Task 9 shipped the SQL script (`scripts/20261004_sim_foundation_and_markdown_core.sql`, all six new tables, every migration guarded) and the patch series.

Corrections found while executing:
1. `PricingFixtures.NewProduct` needs `BarcodeType` (the in-memory database enforces `[Required]`); the fixture code above is corrected in the source.
2. Every migration needs its scaffolded `UpdateData` seed noise stripped (see Plan 1's log, correction 3).
3. Task 6 Step 6: Plan 1 already grants `Cash.*` and `AI.Read` to all `SuperAdmin` roles, so `GrantPricingPermissionsToOwnerRoles` grants only the four `Pricing.*` permissions.
4. Task 4: the `AddSale` anchor was unique (count 1) and the hook compiled cleanly.

## Global Constraints

- Everything from Plan 1's Global Constraints applies (additive only, `TenantID` on tenant tables, PesoWeb controller conventions, new permissions go in `Helpers/Permissions.cs`, branch `Retail_MissionCommerceAI` of `D:\git\Retailo_v1`, never `git add .` there, migrations applied to the local dev database only, "variance" wording, no secrets in git).
- **Guardrails are enforced inside PesoWeb**: on every markdown write and again at sale time. The AI or any caller cannot bypass them.
- **All prices in guardrail checks are net of the product's own `Discount` percent and before tax.** `net = basePrice * (1 - Product.Discount / 100)`. The markdown price replaces `Product.Price` (the base), and `Product.Discount` still applies on top, so the floors must be checked on the net figure.
- Margin floor uses `ProductBatch.Cost`, falling back to `Product.Cost` when the batch has none. No cost (null or 0) means the markdown is rejected (`NO_COST`).
- A markdown targets **one batch** (`BatchId` is required). At sale time it prices exactly the units that FEFO took from that batch; units from other batches sell at the normal price. This protects fresh stock from over-discounting.
- Markdowns apply to **non-variant products only** in this plan (variant products keep their normal price; a known limitation).
- The default autonomy mode is **Off**: a tenant with no pricing policy cannot execute markdowns.
- Default FEFO and near-expiry behaviour of PesoWeb is unchanged.
- There is no expired write-off in PesoWeb today. This plan adds one that logs `EXPIRED_WRITE_OFF` rows to the existing `InventoryTransactions` ledger (quantity out at unit cost), so waste in pesos is measurable and the Plan 1 ledger-drift check stays consistent.
- Tests: xUnit in `D:\git\Retailo_v1\Retailo.Tests`, using `TestAppDbContext(dbName, tenantId)`.

---

## File structure

**PesoWeb repo** (`D:\git\Retailo_v1`), all new unless marked
- `Models/PricingPolicy.cs` (model + `AutonomyModes`)
- `Models/PriceChange.cs` (`PriceChange`, `ActiveMarkdown`, `PriceChangeStatus`, `PriceChangeSource`)
- `Services/MarkdownGuardrails.cs` (pure rules, result types, codes)
- `Services/MarkdownService.cs` (propose, approve, reject, end)
- `Services/MarkdownPricingService.cs` (effective base price at sale time)
- `Services/ExpiryService.cs` (risk report, write-off)
- `DTO/Pricing/PricingDTOs.cs`
- `Controllers/PricingController.cs`, `Controllers/ExpiryController.cs`
- modify: `Services/BusinessEventPublisher.cs` (two event type constants), `Data/AppDBContext.cs` (DbSets), `Program.cs` (DI), `Helpers/Permissions.cs`, `Controllers/SalesController.cs` (constructor + one price hook), `Controllers/AiController.cs` (three read endpoints)
- tests: `Retailo.Tests/Support/PricingFixtures.cs`, `MarkdownGuardrailsTests.cs`, `MarkdownServiceTests.cs`, `MarkdownPricingServiceTests.cs`, `ExpiryServiceTests.cs`
- migrations (generated): `AddPricingPolicy`, `AddPriceLedgerAndMarkdowns`, `GrantPricingPermissionsToOwnerRoles`

**Hackathon repo** (`d:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas`)
- `pesoweb-additions/smoke/pricing-smoke.ps1`
- `pesoweb-additions/patches/plan2/*.patch`
- updates to `pesoweb-additions/README.md` and the spec

---

### Task 1: Pricing policy and guardrail rules

**Files (PesoWeb):**
- Create: `Models/PricingPolicy.cs`, `Services/MarkdownGuardrails.cs`
- Modify: `Data/AppDBContext.cs`
- Test: `Retailo.Tests/MarkdownGuardrailsTests.cs`
- Generated: migration `AddPricingPolicy`

**Interfaces:**
- Produces:
  - `PricingPolicy { int Id, int TenantID, decimal HardMarginFloorPct, decimal SoftMarginFloorPct, decimal MaxDiscountPct, int MaxChangesPerSkuPerHour, string AutonomyMode, DateTime? UpdatedAt }` (one row per tenant)
  - `AutonomyModes.Autonomous = "Autonomous"`, `.Approval = "Approval"`, `.Off = "Off"`, `.All`
  - `GuardrailDecision { Allowed, NeedsApproval, Rejected }`
  - `GuardrailCodes` constants: `Ok, NoPolicy, AutonomyOff, NoCost, NotAMarkdown, ExceedsMaxDiscount, BelowHardFloor, TooManyChanges, BelowSoftFloor, ApprovalMode, BatchUnavailable, RejectedByUser`
  - `GuardrailResult { GuardrailDecision Decision; string Code; string Message }` with `Allow()`, `NeedApproval(code, msg)`, `Reject(code, msg)`
  - `MarkdownGuardrails.NetPrice(decimal basePrice, decimal productDiscountPct)`
  - `MarkdownGuardrails.HardViolation(PricingPolicy p, decimal listNetPrice, decimal newNetPrice, decimal? unitCost)` returns a code or `null`
  - `MarkdownGuardrails.HardLimitsHold(...)` (same arguments) returns `bool`
  - `MarkdownGuardrails.Evaluate(PricingPolicy p, decimal listNetPrice, decimal newNetPrice, decimal? unitCost, int changesLastHour, bool approved = false)` returns `GuardrailResult`
  - `AppDBContext.PricingPolicies`
- Rule order in `Evaluate`: autonomy off, hard limits (no cost, not a markdown, max discount, hard floor), change-rate limit, then (unless `approved`) soft floor, then approval mode.

- [ ] **Step 1: Confirm Plan 1 is done and tag it**

```bash
cd /d/git/Retailo_v1
git branch --show-current        # expect: Retail_MissionCommerceAI
dotnet test Retailo.Tests/Retailo.Tests.csproj    # expect: all Plan 1 tests pass (23)
git status --short | grep -v "^??" | grep -E "Models/|Services/|Controllers/|Retailo.Tests/|Migrations/" || echo "no uncommitted Plan 1 changes"
git tag plan1-complete
```

If Plan 1 tests fail or Plan 1 files are uncommitted, stop and finish Plan 1 first.

- [ ] **Step 2: Write the failing tests**

`Retailo.Tests/MarkdownGuardrailsTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Xunit;

namespace Retailo.Tests;

public class MarkdownGuardrailsTests
{
    // list net price 100, unit cost 60 -> hard floor 63.00, soft floor 69.00, max discount 50%, max 3 changes/hour
    private static PricingPolicy Policy(string mode = AutonomyModes.Autonomous) => new()
    {
        HardMarginFloorPct = 5m, SoftMarginFloorPct = 15m, MaxDiscountPct = 50m,
        MaxChangesPerSkuPerHour = 3, AutonomyMode = mode
    };

    private static GuardrailResult Eval(decimal newNet, decimal? cost = 60m, int changes = 0,
        string mode = AutonomyModes.Autonomous, bool approved = false, decimal listNet = 100m)
        => MarkdownGuardrails.Evaluate(Policy(mode), listNet, newNet, cost, changes, approved);

    [Fact]
    public void Net_price_applies_the_product_discount()
    {
        Assert.Equal(90m, MarkdownGuardrails.NetPrice(100m, 10m));
        Assert.Equal(100m, MarkdownGuardrails.NetPrice(100m, 0m));
    }

    [Fact]
    public void Allows_a_markdown_inside_all_limits()
    {
        var r = Eval(80m);
        Assert.Equal(GuardrailDecision.Allowed, r.Decision);
        Assert.Equal(GuardrailCodes.Ok, r.Code);
    }

    [Fact]
    public void Rejects_below_the_hard_margin_floor()
    {
        var r = Eval(62m);   // 38% off is under the 50% cap, but under cost x 1.05 = 63
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.BelowHardFloor, r.Code);
    }

    [Fact]
    public void Exactly_at_the_hard_floor_is_not_a_hard_violation_but_needs_approval()
    {
        var r = Eval(63m);
        Assert.Equal(GuardrailDecision.NeedsApproval, r.Decision);
        Assert.Equal(GuardrailCodes.BelowSoftFloor, r.Code);
    }

    [Fact]
    public void Between_the_floors_needs_approval_and_approval_unlocks_it()
    {
        Assert.Equal(GuardrailDecision.NeedsApproval, Eval(68m).Decision);
        Assert.Equal(GuardrailDecision.Allowed, Eval(68m, approved: true).Decision);
    }

    [Fact]
    public void Approval_can_never_waive_the_hard_floor()
    {
        var r = Eval(62m, approved: true);
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.BelowHardFloor, r.Code);
    }

    [Fact]
    public void Rejects_a_discount_above_the_maximum_even_when_the_floor_is_fine()
    {
        var r = Eval(45m, cost: 20m);   // 55% off > 50% cap; hard floor would be 21
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.ExceedsMaxDiscount, r.Code);
    }

    [Theory]
    [InlineData(100)]    // same price
    [InlineData(120)]    // price increase
    [InlineData(0)]
    [InlineData(-5)]
    public void Rejects_anything_that_is_not_a_markdown(int newNet)
    {
        var r = Eval(newNet);
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.NotAMarkdown, r.Code);
    }

    [Fact]
    public void Rejects_when_the_change_rate_limit_is_reached()
    {
        Assert.Equal(GuardrailDecision.Allowed, Eval(80m, changes: 2).Decision);
        var r = Eval(80m, changes: 3);
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.TooManyChanges, r.Code);
    }

    [Fact]
    public void Rejects_when_cost_is_missing_or_zero()
    {
        Assert.Equal(GuardrailCodes.NoCost, Eval(80m, cost: null).Code);
        Assert.Equal(GuardrailCodes.NoCost, Eval(80m, cost: 0m).Code);
    }

    [Fact]
    public void Autonomy_off_rejects_everything()
    {
        var r = Eval(80m, mode: AutonomyModes.Off);
        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        Assert.Equal(GuardrailCodes.AutonomyOff, r.Code);
    }

    [Fact]
    public void Approval_mode_always_needs_approval_until_approved()
    {
        var r = Eval(80m, mode: AutonomyModes.Approval);
        Assert.Equal(GuardrailDecision.NeedsApproval, r.Decision);
        Assert.Equal(GuardrailCodes.ApprovalMode, r.Code);
        Assert.Equal(GuardrailDecision.Allowed, Eval(80m, mode: AutonomyModes.Approval, approved: true).Decision);
    }

    [Fact]
    public void Hard_limits_hold_reflects_only_the_hard_rules()
    {
        var p = Policy();
        Assert.True(MarkdownGuardrails.HardLimitsHold(p, 100m, 80m, 60m));
        Assert.True(MarkdownGuardrails.HardLimitsHold(p, 100m, 65m, 60m));    // below soft floor, above hard
        Assert.False(MarkdownGuardrails.HardLimitsHold(p, 100m, 62m, 60m));
        Assert.False(MarkdownGuardrails.HardLimitsHold(p, 100m, 80m, null));
    }
}
```

- [ ] **Step 3: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownGuardrailsTests`
Expected: build FAIL (`PricingPolicy`, `MarkdownGuardrails` not defined).

- [ ] **Step 4: Add the model**

`Models/PricingPolicy.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace GoPosify.Models;

public static class AutonomyModes
{
    public const string Autonomous = "Autonomous";   // execute inside guardrails
    public const string Approval = "Approval";       // every markdown needs a human approval
    public const string Off = "Off";                 // no markdowns may be executed

    public static readonly string[] All = { Autonomous, Approval, Off };
}

[Index(nameof(TenantID), IsUnique = true, Name = "UX_PricingPolicies_Tenant")]
public partial class PricingPolicy
{
    [Key]
    public int Id { get; set; }

    public int TenantID { get; set; }

    // Net price must stay at or above cost x (1 + HardMarginFloorPct/100). Never waivable.
    [Column(TypeName = "decimal(9, 2)")]
    public decimal HardMarginFloorPct { get; set; }

    // Below this (but above the hard floor) a markdown needs approval.
    [Column(TypeName = "decimal(9, 2)")]
    public decimal SoftMarginFloorPct { get; set; }

    [Column(TypeName = "decimal(9, 2)")]
    public decimal MaxDiscountPct { get; set; }

    public int MaxChangesPerSkuPerHour { get; set; }

    [Required]
    [StringLength(20)]
    public string AutonomyMode { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? UpdatedAt { get; set; }
}
```

- [ ] **Step 5: Add the DbSet**

In `Data/AppDBContext.cs`, next to `CashShifts`:

```csharp
    public virtual DbSet<PricingPolicy> PricingPolicies { get; set; }
```

- [ ] **Step 6: Implement the rules**

`Services/MarkdownGuardrails.cs`:

```csharp
using GoPosify.Models;

namespace GoPosify.Services;

public enum GuardrailDecision
{
    Allowed,
    NeedsApproval,
    Rejected
}

public static class GuardrailCodes
{
    public const string Ok = "OK";
    public const string NoPolicy = "NO_POLICY";
    public const string AutonomyOff = "AUTONOMY_OFF";
    public const string NoCost = "NO_COST";
    public const string NotAMarkdown = "NOT_A_MARKDOWN";
    public const string ExceedsMaxDiscount = "EXCEEDS_MAX_DISCOUNT";
    public const string BelowHardFloor = "BELOW_HARD_FLOOR";
    public const string TooManyChanges = "TOO_MANY_CHANGES";
    public const string BelowSoftFloor = "BELOW_SOFT_FLOOR";
    public const string ApprovalMode = "APPROVAL_MODE";
    public const string BatchUnavailable = "BATCH_UNAVAILABLE";
    public const string RejectedByUser = "REJECTED_BY_USER";
}

public sealed class GuardrailResult
{
    public GuardrailDecision Decision { get; init; }
    public string Code { get; init; }
    public string Message { get; init; }

    public static GuardrailResult Allow()
        => new() { Decision = GuardrailDecision.Allowed, Code = GuardrailCodes.Ok, Message = "Within guardrails." };

    public static GuardrailResult NeedApproval(string code, string message)
        => new() { Decision = GuardrailDecision.NeedsApproval, Code = code, Message = message };

    public static GuardrailResult Reject(string code, string message)
        => new() { Decision = GuardrailDecision.Rejected, Code = code, Message = message };
}

// Pure rules. Prices passed in are NET of the product's own discount and before tax.
public static class MarkdownGuardrails
{
    public static decimal NetPrice(decimal basePrice, decimal productDiscountPct)
        => basePrice * (1m - productDiscountPct / 100m);

    // First hard-limit violation code, or null when every hard limit holds. Hard limits can never be waived.
    public static string HardViolation(PricingPolicy p, decimal listNetPrice, decimal newNetPrice, decimal? unitCost)
    {
        if (!unitCost.HasValue || unitCost.Value <= 0m)
        {
            return GuardrailCodes.NoCost;
        }

        if (newNetPrice <= 0m || newNetPrice >= listNetPrice)
        {
            return GuardrailCodes.NotAMarkdown;
        }

        var discountPct = (listNetPrice - newNetPrice) / listNetPrice * 100m;
        if (discountPct > p.MaxDiscountPct)
        {
            return GuardrailCodes.ExceedsMaxDiscount;
        }

        if (newNetPrice < unitCost.Value * (1m + p.HardMarginFloorPct / 100m))
        {
            return GuardrailCodes.BelowHardFloor;
        }

        return null;
    }

    public static bool HardLimitsHold(PricingPolicy p, decimal listNetPrice, decimal newNetPrice, decimal? unitCost)
        => HardViolation(p, listNetPrice, newNetPrice, unitCost) == null;

    public static GuardrailResult Evaluate(PricingPolicy p, decimal listNetPrice, decimal newNetPrice,
        decimal? unitCost, int changesLastHour, bool approved = false)
    {
        if (p.AutonomyMode == AutonomyModes.Off)
        {
            return GuardrailResult.Reject(GuardrailCodes.AutonomyOff, "Pricing autonomy is off for this tenant.");
        }

        var hard = HardViolation(p, listNetPrice, newNetPrice, unitCost);
        if (hard != null)
        {
            return GuardrailResult.Reject(hard, HardMessage(hard, p));
        }

        if (changesLastHour >= p.MaxChangesPerSkuPerHour)
        {
            return GuardrailResult.Reject(GuardrailCodes.TooManyChanges,
                $"Already {changesLastHour} price changes for this product at this branch in the last hour (limit {p.MaxChangesPerSkuPerHour}).");
        }

        if (approved)
        {
            return GuardrailResult.Allow();
        }

        if (newNetPrice < unitCost.Value * (1m + p.SoftMarginFloorPct / 100m))
        {
            return GuardrailResult.NeedApproval(GuardrailCodes.BelowSoftFloor,
                $"Price is below the soft margin floor ({p.SoftMarginFloorPct}%); approval required.");
        }

        if (p.AutonomyMode == AutonomyModes.Approval)
        {
            return GuardrailResult.NeedApproval(GuardrailCodes.ApprovalMode, "This tenant requires approval for every markdown.");
        }

        return GuardrailResult.Allow();
    }

    private static string HardMessage(string code, PricingPolicy p) => code switch
    {
        GuardrailCodes.NoCost => "No unit cost is known for this batch, so the margin floor cannot be checked.",
        GuardrailCodes.NotAMarkdown => "The new price must be lower than the current price and above zero.",
        GuardrailCodes.ExceedsMaxDiscount => $"Discount exceeds the maximum of {p.MaxDiscountPct}%.",
        GuardrailCodes.BelowHardFloor => $"Price is below the hard margin floor ({p.HardMarginFloorPct}% over cost).",
        _ => "Rejected by guardrails."
    };
}
```

- [ ] **Step 7: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownGuardrailsTests`
Expected: all pass (16 test cases).

- [ ] **Step 8: Generate, inspect and apply the migration**

```bash
dotnet ef migrations add AddPricingPolicy --project Retailo.csproj
```

The generated migration must contain **only** `CreateTable("PricingPolicies")` with its unique index (and the matching `DropTable`). Anything else: apply the Plan 1 stop-and-report rule (delete the new migration files, `git checkout -- Migrations/AppDBContextModelSnapshot.cs`, report).

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
```

- [ ] **Step 9: Commit**

```bash
git add Models/PricingPolicy.cs Services/MarkdownGuardrails.cs Data/AppDBContext.cs Retailo.Tests/MarkdownGuardrailsTests.cs Migrations/*AddPricingPolicy*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: pricing policy and markdown guardrail rules"
```

---

### Task 2: Price-change ledger and active-markdown tables

**Files (PesoWeb):**
- Create: `Models/PriceChange.cs`
- Modify: `Data/AppDBContext.cs`, `Services/BusinessEventPublisher.cs`
- Generated: migration `AddPriceLedgerAndMarkdowns`

**Interfaces:**
- Produces:
  - `PriceChange { long Id, int TenantID, int WarehouseId, int ProductId, long? BatchId, decimal PriceBefore, decimal PriceAfter, decimal DiscountPct, string Reason, string Source, string Status, string GuardrailCode, string GuardrailMessage, string PredictionRef, DateTime? EndsAt, int? CreatedBy, DateTime CreatedAt, int? DecidedBy, DateTime? DecidedAt }` (`PriceBefore`/`PriceAfter` are base prices, the same unit as `Product.Price`; `EndsAt` is the requested end of the markdown)
  - `ActiveMarkdown { long Id, int TenantID, int WarehouseId, int ProductId, long BatchId, decimal Price, DateTime StartsAt, DateTime? EndsAt, bool IsActive, long PriceChangeId, string Source }` (`Price` replaces `Product.Price` for units from that batch)
  - `PriceChangeStatus.Applied/PendingApproval/Rejected/Ended`, `PriceChangeSource.Ai/Manual`
  - `AppDBContext.PriceChanges`, `AppDBContext.ActiveMarkdowns`
  - `BusinessEventTypes.PriceChanged = "PriceChanged"`, `BusinessEventTypes.InventoryExpired = "InventoryExpired"`

- [ ] **Step 1: Add the models**

`Models/PriceChange.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace GoPosify.Models;

public static class PriceChangeStatus
{
    public const string Applied = "Applied";
    public const string PendingApproval = "PendingApproval";
    public const string Rejected = "Rejected";
    public const string Ended = "Ended";
}

public static class PriceChangeSource
{
    public const string Ai = "Ai";
    public const string Manual = "Manual";
}

// Append-only audit trail of every markdown request, whatever its outcome.
[Index(nameof(TenantID), nameof(WarehouseId), nameof(ProductId), nameof(CreatedAt), Name = "IX_PriceChanges_Tenant_Branch_Product_Time")]
public partial class PriceChange
{
    [Key]
    public long Id { get; set; }

    public int TenantID { get; set; }

    public int WarehouseId { get; set; }

    public int ProductId { get; set; }

    public long? BatchId { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal PriceBefore { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal PriceAfter { get; set; }

    [Column(TypeName = "decimal(9, 2)")]
    public decimal DiscountPct { get; set; }

    [StringLength(300)]
    public string Reason { get; set; }

    [Required]
    [StringLength(20)]
    public string Source { get; set; }

    [Required]
    [StringLength(20)]
    public string Status { get; set; }

    [StringLength(40)]
    public string GuardrailCode { get; set; }

    [StringLength(300)]
    public string GuardrailMessage { get; set; }

    [StringLength(64)]
    public string PredictionRef { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? EndsAt { get; set; }

    public int? CreatedBy { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime CreatedAt { get; set; }

    public int? DecidedBy { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? DecidedAt { get; set; }
}

// The live state the POS reads. One active row per batch at most.
[Index(nameof(TenantID), nameof(WarehouseId), nameof(ProductId), nameof(IsActive), Name = "IX_ActiveMarkdowns_Tenant_Branch_Product_Active")]
public partial class ActiveMarkdown
{
    [Key]
    public long Id { get; set; }

    public int TenantID { get; set; }

    public int WarehouseId { get; set; }

    public int ProductId { get; set; }

    public long BatchId { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal Price { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime StartsAt { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? EndsAt { get; set; }

    public bool IsActive { get; set; }

    public long PriceChangeId { get; set; }

    [StringLength(20)]
    public string Source { get; set; }
}
```

- [ ] **Step 2: Add DbSets**

In `Data/AppDBContext.cs`, next to `PricingPolicies`:

```csharp
    public virtual DbSet<PriceChange> PriceChanges { get; set; }

    public virtual DbSet<ActiveMarkdown> ActiveMarkdowns { get; set; }
```

- [ ] **Step 3: Add the event type constants**

In `Services/BusinessEventPublisher.cs`, inside `BusinessEventTypes`, add after `CashClosed`:

```csharp
    public const string PriceChanged = "PriceChanged";
    public const string InventoryExpired = "InventoryExpired";
```

- [ ] **Step 4: Build and test**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all tests pass.

- [ ] **Step 5: Generate, inspect and apply the migration**

```bash
dotnet ef migrations add AddPriceLedgerAndMarkdowns --project Retailo.csproj
```

It must contain **only** `CreateTable("PriceChanges")` and `CreateTable("ActiveMarkdowns")` with their indexes. Anything else: stop and report.

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
```

- [ ] **Step 6: Commit**

```bash
git add Models/PriceChange.cs Data/AppDBContext.cs Services/BusinessEventPublisher.cs Migrations/*AddPriceLedgerAndMarkdowns*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: price change ledger and active markdown tables"
```

---

### Task 3: Markdown service (propose, approve, reject, end)

**Files (PesoWeb):**
- Create: `Services/MarkdownService.cs`, `Retailo.Tests/Support/PricingFixtures.cs`
- Modify: `Program.cs`
- Test: `Retailo.Tests/MarkdownServiceTests.cs`

**Interfaces:**
- Consumes: `MarkdownGuardrails`, `GuardrailResult`, `GuardrailCodes`, `PricingPolicy`, `PriceChange`, `ActiveMarkdown`, `IBusinessEventPublisher`, `BusinessEventTypes.PriceChanged`.
- Produces in `GoPosify.Services`:
  - `MarkdownProposal { int WarehouseId, int ProductId, long BatchId, decimal NewPrice, string Reason, string PredictionRef, DateTime? EndsAt }` (`NewPrice` is a **base** price, same unit as `Product.Price`)
  - `MarkdownOutcome { GuardrailDecision Decision, string Code, string Message, long PriceChangeId, long? ActiveMarkdownId }`
  - `IMarkdownService`:
    - `Task<MarkdownOutcome> ProposeAsync(MarkdownProposal p, string source, int? userId, DateTime now)`
    - `Task<MarkdownOutcome> ApproveAsync(long priceChangeId, int userId, DateTime now)`
    - `Task<MarkdownOutcome> RejectAsync(long priceChangeId, int userId, string reason, DateTime now)`
    - `Task<bool> EndAsync(long activeMarkdownId, string reason, DateTime now)`
  - Invalid references (unknown product or batch, non-expiry product, expired batch, empty batch) throw `InvalidOperationException`. Guardrail outcomes never throw; they are returned and recorded in the ledger.
- Test helper produced: `PricingFixtures` (`Policy`, `NewProduct`, `NewBatch`, `Publisher`).

- [ ] **Step 1: Add the test fixtures**

`Retailo.Tests/Support/PricingFixtures.cs`:

```csharp
using GoPosify.Data;
using GoPosify.Models;
using GoPosify.Services;
using Microsoft.AspNetCore.Http;

namespace Retailo.Tests.Support;

public static class PricingFixtures
{
    public static PricingPolicy Policy(string mode = AutonomyModes.Autonomous) => new()
    {
        HardMarginFloorPct = 5m, SoftMarginFloorPct = 15m, MaxDiscountPct = 50m,
        MaxChangesPerSkuPerHour = 3, AutonomyMode = mode
    };

    public static Product NewProduct(decimal price = 100m, decimal cost = 60m, decimal discount = 0m, bool monitorExpiry = true)
        => new()
        {
            ProductName = "Fresh Milk", ProductCode = "MILK-" + Guid.NewGuid().ToString("N")[..6],
            Price = price, Cost = cost, Discount = discount,
            MonitorExpiry = monitorExpiry, BatchTracking = monitorExpiry, ExpiryAlertDays = 30
        };

    public static ProductBatch NewBatch(int productId, DateTime expiry, decimal qty = 20m, decimal cost = 60m, int warehouseId = 1)
        => new()
        {
            WarehouseId = warehouseId, ProductId = productId, BatchNo = "B-" + Guid.NewGuid().ToString("N")[..6],
            ExpiryDate = expiry, QtyOnHand = qty, Cost = cost
        };

    public static IBusinessEventPublisher Publisher(AppDBContext db)
        => new BusinessEventPublisher(db, new HttpContextAccessor { HttpContext = new DefaultHttpContext() });
}
```

- [ ] **Step 2: Write the failing tests**

`Retailo.Tests/MarkdownServiceTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class MarkdownServiceTests
{
    private static readonly DateTime Now = new(2026, 10, 20, 10, 0, 0);

    private sealed class World
    {
        public string DbName;
        public TestAppDbContext Db;
        public MarkdownService Svc;
        public Product Product;
        public ProductBatch Batch;
    }

    private static async Task<World> CreateAsync(PricingPolicy policy = null, decimal productDiscount = 0m,
        int expiryInDays = 3, decimal batchCost = 60m, bool monitorExpiry = true)
    {
        var name = TestAppDbContext.NewDbName();
        var db = new TestAppDbContext(name, 5);
        if (policy != null) db.PricingPolicies.Add(policy);
        var product = PricingFixtures.NewProduct(discount: productDiscount, monitorExpiry: monitorExpiry);
        db.Products.Add(product);
        await db.SaveChangesAsync();
        var batch = PricingFixtures.NewBatch(product.Id, Now.Date.AddDays(expiryInDays), cost: batchCost);
        db.ProductBatches.Add(batch);
        await db.SaveChangesAsync();
        return new World { DbName = name, Db = db, Svc = new MarkdownService(db, PricingFixtures.Publisher(db)), Product = product, Batch = batch };
    }

    private static MarkdownProposal Propose(World w, decimal newPrice, DateTime? endsAt = null) => new()
    {
        WarehouseId = 1, ProductId = w.Product.Id, BatchId = w.Batch.Id, NewPrice = newPrice,
        Reason = "near expiry", PredictionRef = "pred-1", EndsAt = endsAt
    };

    [Fact]
    public async Task Allowed_markdown_creates_active_markdown_ledger_row_and_event()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;

        var o = await w.Svc.ProposeAsync(Propose(w, 80m), PriceChangeSource.Ai, 9, Now);

        Assert.Equal(GuardrailDecision.Allowed, o.Decision);
        var md = Assert.Single(w.Db.ActiveMarkdowns.ToList());
        Assert.True(md.IsActive);
        Assert.Equal(80m, md.Price);
        Assert.Equal(w.Batch.Id, md.BatchId);
        Assert.Equal(o.ActiveMarkdownId, md.Id);
        var pc = Assert.Single(w.Db.PriceChanges.ToList());
        Assert.Equal(PriceChangeStatus.Applied, pc.Status);
        Assert.Equal(100m, pc.PriceBefore);
        Assert.Equal(80m, pc.PriceAfter);
        Assert.Equal(20m, pc.DiscountPct);
        Assert.Equal("pred-1", pc.PredictionRef);
        Assert.Equal(PriceChangeSource.Ai, pc.Source);
        var ev = Assert.Single(w.Db.BusinessEvents.ToList());
        Assert.Equal(BusinessEventTypes.PriceChanged, ev.EventType);
        Assert.Contains("\"kind\":\"markdown\"", ev.PayloadJson);
    }

    [Fact]
    public async Task Below_hard_floor_is_rejected_and_recorded_but_never_applied()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;

        var o = await w.Svc.ProposeAsync(Propose(w, 62m), PriceChangeSource.Ai, 9, Now);

        Assert.Equal(GuardrailDecision.Rejected, o.Decision);
        Assert.Equal(GuardrailCodes.BelowHardFloor, o.Code);
        Assert.Empty(w.Db.ActiveMarkdowns.ToList());
        Assert.Empty(w.Db.BusinessEvents.ToList());
        var pc = Assert.Single(w.Db.PriceChanges.ToList());
        Assert.Equal(PriceChangeStatus.Rejected, pc.Status);
        Assert.Equal(GuardrailCodes.BelowHardFloor, pc.GuardrailCode);
    }

    [Fact]
    public async Task Soft_floor_waits_for_approval_then_applies()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;

        var o = await w.Svc.ProposeAsync(Propose(w, 68m), PriceChangeSource.Ai, 9, Now);
        Assert.Equal(GuardrailDecision.NeedsApproval, o.Decision);
        Assert.Null(o.ActiveMarkdownId);
        Assert.Empty(w.Db.ActiveMarkdowns.ToList());
        Assert.Equal(PriceChangeStatus.PendingApproval, w.Db.PriceChanges.Single().Status);

        var a = await w.Svc.ApproveAsync(o.PriceChangeId, 42, Now.AddMinutes(5));

        Assert.Equal(GuardrailDecision.Allowed, a.Decision);
        var md = Assert.Single(w.Db.ActiveMarkdowns.ToList());
        Assert.Equal(68m, md.Price);
        var pc = w.Db.PriceChanges.Single();
        Assert.Equal(PriceChangeStatus.Applied, pc.Status);
        Assert.Equal(42, pc.DecidedBy);
        Assert.Contains(w.Db.BusinessEvents.ToList(), e => e.EventType == BusinessEventTypes.PriceChanged);
    }

    [Fact]
    public async Task Approval_cannot_waive_a_hard_floor_that_tightened_in_the_meantime()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        var o = await w.Svc.ProposeAsync(Propose(w, 68m), PriceChangeSource.Ai, 9, Now);
        var policy = w.Db.PricingPolicies.Single();
        policy.HardMarginFloorPct = 20m;      // new hard floor = 72 > 68
        await w.Db.SaveChangesAsync();

        var a = await w.Svc.ApproveAsync(o.PriceChangeId, 42, Now.AddMinutes(5));

        Assert.Equal(GuardrailDecision.Rejected, a.Decision);
        Assert.Equal(GuardrailCodes.BelowHardFloor, a.Code);
        Assert.Empty(w.Db.ActiveMarkdowns.ToList());
        Assert.Equal(PriceChangeStatus.Rejected, w.Db.PriceChanges.Single().Status);
    }

    [Fact]
    public async Task Pending_change_can_be_rejected_by_a_person()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        var o = await w.Svc.ProposeAsync(Propose(w, 68m), PriceChangeSource.Ai, 9, Now);

        var r = await w.Svc.RejectAsync(o.PriceChangeId, 42, "not today", Now);

        Assert.Equal(GuardrailDecision.Rejected, r.Decision);
        var pc = w.Db.PriceChanges.Single();
        Assert.Equal(GuardrailCodes.RejectedByUser, pc.GuardrailCode);
        Assert.Equal("not today", pc.GuardrailMessage);
        Assert.Empty(w.Db.ActiveMarkdowns.ToList());
    }

    [Fact]
    public async Task No_policy_rejects_with_NO_POLICY()
    {
        var w = await CreateAsync(policy: null);
        await using var _ = w.Db;

        var o = await w.Svc.ProposeAsync(Propose(w, 80m), PriceChangeSource.Manual, 9, Now);

        Assert.Equal(GuardrailDecision.Rejected, o.Decision);
        Assert.Equal(GuardrailCodes.NoPolicy, o.Code);
        Assert.Equal(PriceChangeStatus.Rejected, w.Db.PriceChanges.Single().Status);
    }

    [Fact]
    public async Task Autonomy_off_rejects()
    {
        var w = await CreateAsync(PricingFixtures.Policy(AutonomyModes.Off));
        await using var _ = w.Db;

        var o = await w.Svc.ProposeAsync(Propose(w, 80m), PriceChangeSource.Ai, 9, Now);

        Assert.Equal(GuardrailCodes.AutonomyOff, o.Code);
        Assert.Empty(w.Db.ActiveMarkdowns.ToList());
    }

    [Fact]
    public async Task Fourth_change_inside_an_hour_is_rejected_but_an_hour_later_is_fine()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        foreach (var price in new[] { 90m, 89m, 88m })
        {
            Assert.Equal(GuardrailDecision.Allowed, (await w.Svc.ProposeAsync(Propose(w, price), PriceChangeSource.Ai, 9, Now)).Decision);
        }

        var blocked = await w.Svc.ProposeAsync(Propose(w, 87m), PriceChangeSource.Ai, 9, Now.AddMinutes(30));
        Assert.Equal(GuardrailCodes.TooManyChanges, blocked.Code);

        var later = await w.Svc.ProposeAsync(Propose(w, 86m), PriceChangeSource.Ai, 9, Now.AddMinutes(61));
        Assert.Equal(GuardrailDecision.Allowed, later.Decision);
    }

    [Fact]
    public async Task A_new_markdown_on_the_same_batch_supersedes_the_old_one()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        await w.Svc.ProposeAsync(Propose(w, 90m), PriceChangeSource.Ai, 9, Now);
        await w.Svc.ProposeAsync(Propose(w, 85m), PriceChangeSource.Ai, 9, Now.AddMinutes(10));

        var all = w.Db.ActiveMarkdowns.OrderBy(m => m.Id).ToList();
        Assert.Equal(2, all.Count);
        Assert.False(all[0].IsActive);
        Assert.NotNull(all[0].EndsAt);
        Assert.True(all[1].IsActive);
        Assert.Equal(85m, all[1].Price);
    }

    [Fact]
    public async Task Product_discount_is_included_when_checking_the_floor()
    {
        // list 100 with a 10% product discount -> list net 90. Batch cost 80 -> hard floor 84.
        var w = await CreateAsync(PricingFixtures.Policy(), productDiscount: 10m, batchCost: 80m);
        await using var _ = w.Db;

        var rejected = await w.Svc.ProposeAsync(Propose(w, 90m), PriceChangeSource.Ai, 9, Now);   // net 81 < 84
        Assert.Equal(GuardrailCodes.BelowHardFloor, rejected.Code);

        var needsApproval = await w.Svc.ProposeAsync(Propose(w, 95m), PriceChangeSource.Ai, 9, Now);   // net 85.5, soft floor 92
        Assert.Equal(GuardrailDecision.NeedsApproval, needsApproval.Decision);
    }

    [Fact]
    public async Task Invalid_targets_throw_instead_of_producing_ledger_noise()
    {
        var expired = await CreateAsync(PricingFixtures.Policy(), expiryInDays: -1);
        await using (expired.Db)
            await Assert.ThrowsAsync<InvalidOperationException>(() => expired.Svc.ProposeAsync(Propose(expired, 80m), PriceChangeSource.Ai, 9, Now));

        var plain = await CreateAsync(PricingFixtures.Policy(), monitorExpiry: false);
        await using (plain.Db)
            await Assert.ThrowsAsync<InvalidOperationException>(() => plain.Svc.ProposeAsync(Propose(plain, 80m), PriceChangeSource.Ai, 9, Now));

        var empty = await CreateAsync(PricingFixtures.Policy());
        await using (empty.Db)
        {
            empty.Batch.QtyOnHand = 0;
            await empty.Db.SaveChangesAsync();
            await Assert.ThrowsAsync<InvalidOperationException>(() => empty.Svc.ProposeAsync(Propose(empty, 80m), PriceChangeSource.Ai, 9, Now));
        }

        var unknown = await CreateAsync(PricingFixtures.Policy());
        await using (unknown.Db)
        {
            var p = Propose(unknown, 80m);
            p.BatchId = 999999;
            await Assert.ThrowsAsync<InvalidOperationException>(() => unknown.Svc.ProposeAsync(p, PriceChangeSource.Ai, 9, Now));
            Assert.Empty(unknown.Db.PriceChanges.ToList());
        }
    }

    [Fact]
    public async Task Another_tenant_cannot_mark_down_this_tenants_batch()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        await using var other = new TestAppDbContext(w.DbName, 6);
        var svc = new MarkdownService(other, PricingFixtures.Publisher(other));

        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.ProposeAsync(Propose(w, 80m), PriceChangeSource.Ai, 9, Now));
    }

    [Fact]
    public async Task End_deactivates_records_a_restore_and_publishes_an_event_once()
    {
        var w = await CreateAsync(PricingFixtures.Policy());
        await using var _ = w.Db;
        var o = await w.Svc.ProposeAsync(Propose(w, 80m), PriceChangeSource.Ai, 9, Now);

        Assert.True(await w.Svc.EndAsync(o.ActiveMarkdownId.Value, "sold out", Now.AddHours(1)));
        Assert.False(await w.Svc.EndAsync(o.ActiveMarkdownId.Value, "again", Now.AddHours(2)));

        Assert.False(w.Db.ActiveMarkdowns.Single().IsActive);
        Assert.Contains(w.Db.PriceChanges.ToList(), c => c.Status == PriceChangeStatus.Ended && c.PriceAfter == 100m);
        var events = w.Db.BusinessEvents.ToList();
        Assert.Equal(2, events.Count);
        Assert.Contains(events, e => e.PayloadJson.Contains("\"kind\":\"restore\""));
    }
}
```

- [ ] **Step 3: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownServiceTests`
Expected: build FAIL (`MarkdownService` not defined).

- [ ] **Step 4: Implement the service**

`Services/MarkdownService.cs`:

```csharp
using GoPosify.Data;
using GoPosify.Models;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Services;

public sealed class MarkdownProposal
{
    public int WarehouseId { get; set; }
    public int ProductId { get; set; }
    public long BatchId { get; set; }
    public decimal NewPrice { get; set; }          // base price, same unit as Product.Price
    public string Reason { get; set; }
    public string PredictionRef { get; set; }
    public DateTime? EndsAt { get; set; }
}

public sealed class MarkdownOutcome
{
    public GuardrailDecision Decision { get; set; }
    public string Code { get; set; }
    public string Message { get; set; }
    public long PriceChangeId { get; set; }
    public long? ActiveMarkdownId { get; set; }
}

public interface IMarkdownService
{
    Task<MarkdownOutcome> ProposeAsync(MarkdownProposal p, string source, int? userId, DateTime now);
    Task<MarkdownOutcome> ApproveAsync(long priceChangeId, int userId, DateTime now);
    Task<MarkdownOutcome> RejectAsync(long priceChangeId, int userId, string reason, DateTime now);
    Task<bool> EndAsync(long activeMarkdownId, string reason, DateTime now);
}

public sealed class MarkdownService : IMarkdownService
{
    private readonly AppDBContext _db;
    private readonly IBusinessEventPublisher _events;

    public MarkdownService(AppDBContext db, IBusinessEventPublisher events)
    {
        _db = db;
        _events = events;
    }

    public async Task<MarkdownOutcome> ProposeAsync(MarkdownProposal p, string source, int? userId, DateTime now)
    {
        var (product, batch) = await LoadTargetsAsync(p.WarehouseId, p.ProductId, p.BatchId, now);
        var policy = await _db.PricingPolicies.AsNoTracking().FirstOrDefaultAsync();

        GuardrailResult result;
        if (policy == null)
        {
            result = GuardrailResult.Reject(GuardrailCodes.NoPolicy, "No pricing policy is configured for this tenant.");
        }
        else
        {
            var changes = await CountRecentChangesAsync(p.WarehouseId, p.ProductId, now, null);
            result = MarkdownGuardrails.Evaluate(
                policy,
                MarkdownGuardrails.NetPrice(product.Price, product.Discount),
                MarkdownGuardrails.NetPrice(p.NewPrice, product.Discount),
                ResolveCost(batch, product),
                changes);
        }

        var change = new PriceChange
        {
            WarehouseId = p.WarehouseId,
            ProductId = p.ProductId,
            BatchId = p.BatchId,
            PriceBefore = product.Price,
            PriceAfter = p.NewPrice,
            DiscountPct = product.Price > 0 ? (product.Price - p.NewPrice) / product.Price * 100m : 0m,
            Reason = Trim(p.Reason, 300),
            Source = source,
            Status = result.Decision switch
            {
                GuardrailDecision.Allowed => PriceChangeStatus.Applied,
                GuardrailDecision.NeedsApproval => PriceChangeStatus.PendingApproval,
                _ => PriceChangeStatus.Rejected
            },
            GuardrailCode = result.Code,
            GuardrailMessage = Trim(result.Message, 300),
            PredictionRef = Trim(p.PredictionRef, 64),
            EndsAt = p.EndsAt,
            CreatedBy = userId,
            CreatedAt = now
        };
        _db.PriceChanges.Add(change);
        await _db.SaveChangesAsync();

        long? activeId = null;
        if (result.Decision == GuardrailDecision.Allowed)
        {
            activeId = await ActivateAsync(change, now);
        }

        return Outcome(result, change.Id, activeId);
    }

    public async Task<MarkdownOutcome> ApproveAsync(long priceChangeId, int userId, DateTime now)
    {
        var change = await GetPendingAsync(priceChangeId);

        Product product;
        ProductBatch batch;
        try
        {
            var t = await LoadTargetsAsync(change.WarehouseId, change.ProductId, change.BatchId.Value, now);
            product = t.Product;
            batch = t.Batch;
        }
        catch (InvalidOperationException ex)
        {
            return await FinishRejectedAsync(change, GuardrailCodes.BatchUnavailable, ex.Message, userId, now);
        }

        var policy = await _db.PricingPolicies.AsNoTracking().FirstOrDefaultAsync();
        if (policy == null)
        {
            return await FinishRejectedAsync(change, GuardrailCodes.NoPolicy, "No pricing policy is configured for this tenant.", userId, now);
        }

        var changes = await CountRecentChangesAsync(change.WarehouseId, change.ProductId, now, change.Id);
        var result = MarkdownGuardrails.Evaluate(
            policy,
            MarkdownGuardrails.NetPrice(product.Price, product.Discount),
            MarkdownGuardrails.NetPrice(change.PriceAfter, product.Discount),
            ResolveCost(batch, product),
            changes,
            approved: true);

        if (result.Decision != GuardrailDecision.Allowed)
        {
            return await FinishRejectedAsync(change, result.Code, result.Message, userId, now);
        }

        change.Status = PriceChangeStatus.Applied;
        change.GuardrailCode = GuardrailCodes.Ok;
        change.GuardrailMessage = "Approved.";
        change.DecidedBy = userId;
        change.DecidedAt = now;
        await _db.SaveChangesAsync();

        var activeId = await ActivateAsync(change, now);
        return Outcome(GuardrailResult.Allow(), change.Id, activeId);
    }

    public async Task<MarkdownOutcome> RejectAsync(long priceChangeId, int userId, string reason, DateTime now)
    {
        var change = await GetPendingAsync(priceChangeId);
        return await FinishRejectedAsync(change, GuardrailCodes.RejectedByUser,
            string.IsNullOrWhiteSpace(reason) ? "Rejected by approver." : reason, userId, now);
    }

    public async Task<bool> EndAsync(long activeMarkdownId, string reason, DateTime now)
    {
        var md = await _db.ActiveMarkdowns.FirstOrDefaultAsync(m => m.Id == activeMarkdownId && m.IsActive);
        if (md == null)
        {
            return false;
        }

        md.IsActive = false;
        md.EndsAt = now;

        var listPrice = await _db.Products.AsNoTracking().Where(x => x.Id == md.ProductId).Select(x => x.Price).FirstOrDefaultAsync();
        var restore = new PriceChange
        {
            WarehouseId = md.WarehouseId,
            ProductId = md.ProductId,
            BatchId = md.BatchId,
            PriceBefore = md.Price,
            PriceAfter = listPrice,
            DiscountPct = 0m,
            Reason = Trim(reason, 300),
            Source = md.Source ?? PriceChangeSource.Manual,
            Status = PriceChangeStatus.Ended,
            GuardrailCode = GuardrailCodes.Ok,
            GuardrailMessage = "Markdown ended.",
            CreatedAt = now
        };
        _db.PriceChanges.Add(restore);
        await _db.SaveChangesAsync();

        _events.Publish(BusinessEventTypes.PriceChanged, md.WarehouseId, $"pc-{restore.Id}",
            new { kind = "restore", priceChangeId = restore.Id, activeMarkdownId = md.Id, productId = md.ProductId, batchId = md.BatchId, priceBefore = md.Price, priceAfter = listPrice },
            now);
        await _db.SaveChangesAsync();
        return true;
    }

    private async Task<(Product Product, ProductBatch Batch)> LoadTargetsAsync(int warehouseId, int productId, long batchId, DateTime now)
    {
        var product = await _db.Products.FirstOrDefaultAsync(x => x.Id == productId)
            ?? throw new InvalidOperationException("Product not found.");
        if (!product.MonitorExpiry)
        {
            throw new InvalidOperationException("Product is not expiry-tracked, so it cannot be marked down per batch.");
        }

        var batch = await _db.ProductBatches.FirstOrDefaultAsync(b => b.Id == batchId && b.WarehouseId == warehouseId && b.ProductId == productId)
            ?? throw new InvalidOperationException("Batch not found for this branch and product.");
        if (batch.QtyOnHand <= 0)
        {
            throw new InvalidOperationException("Batch has no stock.");
        }

        if (batch.ExpiryDate.HasValue && batch.ExpiryDate.Value.Date < now.Date)
        {
            throw new InvalidOperationException("Batch is already expired.");
        }

        return (product, batch);
    }

    private static decimal? ResolveCost(ProductBatch batch, Product product)
    {
        var cost = batch.Cost ?? product.Cost;
        return cost > 0m ? cost : null;
    }

    private Task<int> CountRecentChangesAsync(int warehouseId, int productId, DateTime now, long? excludeId)
    {
        var since = now.AddHours(-1);
        return _db.PriceChanges.CountAsync(c =>
            c.WarehouseId == warehouseId && c.ProductId == productId && c.CreatedAt > since
            && (c.Status == PriceChangeStatus.Applied || c.Status == PriceChangeStatus.PendingApproval)
            && (!excludeId.HasValue || c.Id != excludeId.Value));
    }

    private async Task<PriceChange> GetPendingAsync(long priceChangeId)
        => await _db.PriceChanges.FirstOrDefaultAsync(c => c.Id == priceChangeId && c.Status == PriceChangeStatus.PendingApproval)
           ?? throw new InvalidOperationException("Price change not found or not pending.");

    private async Task<MarkdownOutcome> FinishRejectedAsync(PriceChange change, string code, string message, int? userId, DateTime now)
    {
        change.Status = PriceChangeStatus.Rejected;
        change.GuardrailCode = code;
        change.GuardrailMessage = Trim(message, 300);
        change.DecidedBy = userId;
        change.DecidedAt = now;
        await _db.SaveChangesAsync();
        return Outcome(GuardrailResult.Reject(code, message), change.Id, null);
    }

    private async Task<long> ActivateAsync(PriceChange change, DateTime now)
    {
        var existing = await _db.ActiveMarkdowns
            .Where(m => m.IsActive && m.WarehouseId == change.WarehouseId && m.ProductId == change.ProductId && m.BatchId == change.BatchId.Value)
            .ToListAsync();
        foreach (var e in existing)
        {
            e.IsActive = false;
            e.EndsAt = now;
        }

        var md = new ActiveMarkdown
        {
            WarehouseId = change.WarehouseId,
            ProductId = change.ProductId,
            BatchId = change.BatchId.Value,
            Price = change.PriceAfter,
            StartsAt = now,
            EndsAt = change.EndsAt,
            IsActive = true,
            PriceChangeId = change.Id,
            Source = change.Source
        };
        _db.ActiveMarkdowns.Add(md);
        await _db.SaveChangesAsync();

        _events.Publish(BusinessEventTypes.PriceChanged, change.WarehouseId, $"pc-{change.Id}",
            new
            {
                kind = "markdown", priceChangeId = change.Id, activeMarkdownId = md.Id, productId = change.ProductId,
                batchId = change.BatchId, priceBefore = change.PriceBefore, priceAfter = change.PriceAfter,
                discountPct = change.DiscountPct, source = change.Source, predictionRef = change.PredictionRef
            },
            now);
        await _db.SaveChangesAsync();
        return md.Id;
    }

    private static MarkdownOutcome Outcome(GuardrailResult r, long priceChangeId, long? activeId) => new()
    {
        Decision = r.Decision, Code = r.Code, Message = r.Message, PriceChangeId = priceChangeId, ActiveMarkdownId = activeId
    };

    private static string Trim(string s, int max) => string.IsNullOrEmpty(s) || s.Length <= max ? s : s.Substring(0, max);
}
```

- [ ] **Step 5: Register in DI**

In `Program.cs`, after the `ILedgerService` registration:

```csharp
builder.Services.AddScoped<IMarkdownService, MarkdownService>();
```

- [ ] **Step 6: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownServiceTests`
Expected: all pass (13 tests).

- [ ] **Step 7: Commit**

```bash
git add Services/MarkdownService.cs Retailo.Tests/Support/PricingFixtures.cs Retailo.Tests/MarkdownServiceTests.cs Program.cs
git commit -m "feat: markdown service with guardrails, approval, and price ledger"
```

---

### Task 4: Sale-time markdown pricing and the AddSale hook

**Files (PesoWeb):**
- Create: `Services/MarkdownPricingService.cs`
- Modify: `Program.cs`, `Controllers/SalesController.cs`
- Test: `Retailo.Tests/MarkdownPricingServiceTests.cs`

**Interfaces:**
- Consumes: `ActiveMarkdown`, `PricingPolicy`, `MarkdownGuardrails.NetPrice/HardLimitsHold`, `AutonomyModes`, `BatchConsumptionItem` (`GoPosify.Services.Interfaces`).
- Produces: `IMarkdownPricingService.EffectiveBasePriceAsync(int warehouseId, Product product, IReadOnlyList<BatchConsumptionItem> consumed, DateTime now)` returns the quantity-weighted **base** price for the units FEFO consumed. It returns `product.Price` when nothing applies. A markdown is honored for a batch only when it is active, started, not ended, the tenant policy is not `Off`, and the hard limits still hold against that batch's cost (re-checked at sale time).

- [ ] **Step 1: Write the failing tests**

`Retailo.Tests/MarkdownPricingServiceTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using GoPosify.Services.Interfaces;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class MarkdownPricingServiceTests
{
    private static readonly DateTime Now = new(2026, 10, 20, 10, 0, 0);

    private static async Task<(TestAppDbContext db, MarkdownPricingService svc, Product product)> CreateAsync(PricingPolicy policy)
    {
        var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        if (policy != null) db.PricingPolicies.Add(policy);
        var product = PricingFixtures.NewProduct(price: 100m, cost: 60m);
        db.Products.Add(product);
        await db.SaveChangesAsync();
        return (db, new MarkdownPricingService(db), product);
    }

    private static ActiveMarkdown Md(int productId, long batchId, decimal price, bool active = true,
        DateTime? starts = null, DateTime? ends = null, int warehouseId = 1) => new()
    {
        WarehouseId = warehouseId, ProductId = productId, BatchId = batchId, Price = price, IsActive = active,
        StartsAt = starts ?? Now.AddHours(-1), EndsAt = ends, Source = PriceChangeSource.Ai
    };

    private static BatchConsumptionItem Used(long batchId, decimal qty, decimal cost = 60m)
        => new() { BatchId = batchId, Quantity = qty, UnitCost = cost };

    [Fact]
    public async Task No_markdown_means_the_normal_price()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, Array.Empty<BatchConsumptionItem>(), Now));
    }

    [Fact]
    public async Task Markdown_prices_the_units_taken_from_its_batch()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m));
        await db.SaveChangesAsync();

        Assert.Equal(80m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
    }

    [Fact]
    public async Task A_line_spanning_two_batches_gets_the_weighted_price()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m));      // marked batch
        await db.SaveChangesAsync();

        // 1 unit from the marked batch (80) + 3 units from a fresh batch (100) = 380 / 4
        var price = await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 1), Used(12, 3) }, Now);

        Assert.Equal(95m, price);
    }

    [Fact]
    public async Task Autonomy_off_is_a_kill_switch_for_existing_markdowns()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy(AutonomyModes.Off));
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m));
        await db.SaveChangesAsync();

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
    }

    [Fact]
    public async Task Missing_policy_means_no_markdown_is_honored()
    {
        var (db, svc, p) = await CreateAsync(null);
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m));
        await db.SaveChangesAsync();

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
    }

    [Theory]
    [InlineData(false, -60, null)]   // inactive
    [InlineData(true, 60, null)]     // starts in the future
    [InlineData(true, -60, -1)]      // already ended (EndsAt one minute ago)
    public async Task Inactive_future_or_ended_markdowns_are_ignored(bool active, int startsMinutesFromNow, int? endsMinutesFromNow)
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m, active,
            starts: Now.AddMinutes(startsMinutesFromNow),
            ends: endsMinutesFromNow.HasValue ? Now.AddMinutes(endsMinutesFromNow.Value) : null));
        await db.SaveChangesAsync();

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
    }

    [Fact]
    public async Task A_markdown_that_no_longer_clears_the_hard_floor_is_ignored_per_batch()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m));      // fine at cost 60 (floor 63)
        db.ActiveMarkdowns.Add(Md(p.Id, 12, 80m));      // batch 12 cost is 78 -> floor 81.9 -> unsafe
        await db.SaveChangesAsync();

        var price = await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 1, cost: 60m), Used(12, 1, cost: 78m) }, Now);

        Assert.Equal(90m, price);    // (80 + 100) / 2
    }

    [Fact]
    public async Task Markdowns_from_another_branch_do_not_apply()
    {
        var (db, svc, p) = await CreateAsync(PricingFixtures.Policy());
        await using var _ = db;
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 80m, warehouseId: 2));
        await db.SaveChangesAsync();

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 2) }, Now));
    }

    [Fact]
    public async Task Product_discount_is_respected_when_rechecking_the_floor()
    {
        var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        await using var _ = db;
        db.PricingPolicies.Add(PricingFixtures.Policy());
        var p = PricingFixtures.NewProduct(price: 100m, cost: 80m, discount: 10m);   // list net 90, floor net 84
        db.Products.Add(p);
        await db.SaveChangesAsync();
        db.ActiveMarkdowns.Add(Md(p.Id, 11, 90m));      // net 81 < 84 -> unsafe even though 90 > 84 as a base
        await db.SaveChangesAsync();
        var svc = new MarkdownPricingService(db);

        Assert.Equal(100m, await svc.EffectiveBasePriceAsync(1, p, new[] { Used(11, 1, cost: 80m) }, Now));
    }
}
```

- [ ] **Step 2: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownPricingServiceTests`
Expected: build FAIL (`MarkdownPricingService` not defined).

- [ ] **Step 3: Implement the resolver**

`Services/MarkdownPricingService.cs`:

```csharp
using GoPosify.Data;
using GoPosify.Models;
using GoPosify.Services.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Services;

public interface IMarkdownPricingService
{
    // Quantity-weighted BASE price (the unit of Product.Price) for the units FEFO consumed from these batches.
    Task<decimal> EffectiveBasePriceAsync(int warehouseId, Product product, IReadOnlyList<BatchConsumptionItem> consumed, DateTime now);
}

public sealed class MarkdownPricingService : IMarkdownPricingService
{
    private readonly AppDBContext _db;

    public MarkdownPricingService(AppDBContext db)
    {
        _db = db;
    }

    public async Task<decimal> EffectiveBasePriceAsync(int warehouseId, Product product, IReadOnlyList<BatchConsumptionItem> consumed, DateTime now)
    {
        if (consumed == null || consumed.Count == 0)
        {
            return product.Price;
        }

        var batchIds = consumed.Select(c => c.BatchId).ToList();
        var markdowns = await _db.ActiveMarkdowns.AsNoTracking()
            .Where(m => m.IsActive && m.WarehouseId == warehouseId && m.ProductId == product.Id
                        && batchIds.Contains(m.BatchId) && m.StartsAt <= now && (m.EndsAt == null || m.EndsAt > now))
            .ToListAsync();
        if (markdowns.Count == 0)
        {
            return product.Price;
        }

        var policy = await _db.PricingPolicies.AsNoTracking().FirstOrDefaultAsync();
        if (policy == null || policy.AutonomyMode == AutonomyModes.Off)
        {
            return product.Price;   // the policy is the kill switch
        }

        var listNet = MarkdownGuardrails.NetPrice(product.Price, product.Discount);
        decimal totalQty = 0m, totalValue = 0m;

        foreach (var c in consumed)
        {
            var price = product.Price;
            var md = markdowns.FirstOrDefault(m => m.BatchId == c.BatchId);
            if (md != null)
            {
                var cost = c.UnitCost > 0m ? c.UnitCost : (product.Cost > 0m ? product.Cost : (decimal?)null);
                var newNet = MarkdownGuardrails.NetPrice(md.Price, product.Discount);
                if (MarkdownGuardrails.HardLimitsHold(policy, listNet, newNet, cost))
                {
                    price = md.Price;
                }
            }

            totalQty += c.Quantity;
            totalValue += price * c.Quantity;
        }

        return totalQty <= 0m ? product.Price : totalValue / totalQty;
    }
}
```

- [ ] **Step 4: Register in DI**

In `Program.cs`, after `IMarkdownService`:

```csharp
builder.Services.AddScoped<IMarkdownPricingService, MarkdownPricingService>();
```

- [ ] **Step 5: Run the unit tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter MarkdownPricingServiceTests`
Expected: all pass (11 test cases).

- [ ] **Step 6: Hook `AddSale` (two edits in `Controllers/SalesController.cs`)**

(a) Constructor. After Plan 1 the signature ends `IDocService docService, IBusinessEventPublisher events) : base(dbContext)`. Change it to:

```csharp
        private readonly IMarkdownPricingService _markdownPricing;
        public SalesController(AppDBContext dbContext, IStockService stockService, IInventoryBatchService inventoryBatchService, ITransactionService transactionService, IDocService docService, IBusinessEventPublisher events, IMarkdownPricingService markdownPricing) : base(dbContext)
```

and add `_markdownPricing = markdownPricing;` in the constructor body next to `_events = events;`.

(b) Price the non-variant line from the consumed batches. In `AddSale`, find this exact block (it is in the `else` branch for products **without** variants, immediately after the non-batch `ApplyNonBatchStockDeltaAsync` call; the variant branch uses `variant.Price` and must not be touched):

```csharp
                        salePrice = General.CalculateSalePrice(product.Price, product.Discount, product.TaxMethod, product.Tax);
                        newSaleDetail.TaxTotal = General.CalculateTax(product.Price, product.Discount, product.TaxMethod, product.Tax);
                        newSaleDetail.DiscountTotal = General.CalculateDiscount(product.Price, product.Discount);
                        newSaleDetail.SalePrice = salePrice;
                        newSaleDetail.Price = product.Price;
```

Replace it with:

```csharp
                        // Agentic markdowns: FEFO has already chosen the batches; price the units from each batch,
                        // honoring an active markdown only while the guardrails still hold.
                        var basePrice = product.Price;
                        if (pendingBatchAllocations.TryGetValue(newSaleDetail, out var consumedForPrice))
                        {
                            basePrice = await _markdownPricing.EffectiveBasePriceAsync(newSale.WarehouseId, product, consumedForPrice, CurrentDateTime());
                        }

                        salePrice = General.CalculateSalePrice(basePrice, product.Discount, product.TaxMethod, product.Tax);
                        newSaleDetail.TaxTotal = General.CalculateTax(basePrice, product.Discount, product.TaxMethod, product.Tax);
                        newSaleDetail.DiscountTotal = General.CalculateDiscount(basePrice, product.Discount);
                        newSaleDetail.SalePrice = salePrice;
                        newSaleDetail.Price = basePrice;
```

Confirm the block is unique: `grep -c "salePrice = General.CalculateSalePrice(product.Price" Controllers/SalesController.cs` must print `1` before the edit (other actions that edit sales use different variable names; if the count is not 1, stop and report).

- [ ] **Step 7: Build and run the whole suite**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all tests pass.

- [ ] **Step 8: Commit**

```bash
git add Services/MarkdownPricingService.cs Program.cs Controllers/SalesController.cs Retailo.Tests/MarkdownPricingServiceTests.cs
git commit -m "feat: price units from active markdowns at sale time, guardrails re-checked"
```

---

### Task 5: Expiry risk report and expired-stock write-off

**Files (PesoWeb):**
- Create: `Services/ExpiryService.cs`
- Modify: `Program.cs`
- Test: `Retailo.Tests/ExpiryServiceTests.cs`

**Interfaces:**
- Consumes: `ProductBatch`, `Product`, `InventoryTransaction`, `ActiveMarkdown`, `IBusinessEventPublisher`, `BusinessEventTypes.InventoryExpired`, `IInventoryBatchService.SyncWarehouseCacheAsync(int tenantId, int warehouseId, int productId, int? variantId)`.
- Produces in `GoPosify.Services`:
  - `ExpiryStatus.Normal/ExpiringSoon/Critical/Expired`; `ExpiryTransactionTypes.WriteOff = "EXPIRED_WRITE_OFF"`
  - `ExpiryBatchRow { int WarehouseId, int ProductId, string ProductName, long BatchId, string BatchNo, DateTime ExpiryDate, int DaysLeft, decimal QtyOnHand, decimal UnitCost, decimal MoneyAtRisk, string Status }`
  - `ExpiryRiskSummary { int WarehouseId, decimal AtRiskPesos, decimal ExpiredUnwrittenPesos, decimal WrittenOffPesos, int BatchesAtRisk }`
  - `ExpiryRiskReport { List<ExpiryBatchRow> Batches, List<ExpiryRiskSummary> Summaries }` (batches are the non-`Normal` ones, nearest expiry first)
  - `WriteOffResult { int Batches, decimal Units, decimal Pesos }`
  - `IExpiryService.GetRiskAsync(IReadOnlyCollection<int> warehouseIds, DateTime today, int criticalDays = 2)` (`null` = all branches)
  - `IExpiryService.WriteOffExpiredAsync(IReadOnlyCollection<int> warehouseIds, DateTime now, int? updatedBy)` (idempotent)
- Status rules: `DaysLeft < 0` Expired; `<= criticalDays` Critical; `<= ExpiryAlertDays` (30 when unset) ExpiringSoon; else Normal. Money at risk is `QtyOnHand x (batch cost, else product cost)`. Waste in pesos is `QtyOut x UnitCost` on `EXPIRED_WRITE_OFF` ledger rows.

- [ ] **Step 1: Write the failing tests**

`Retailo.Tests/ExpiryServiceTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class ExpiryServiceTests
{
    private static readonly DateTime Today = new(2026, 10, 20);

    private static ExpiryService Svc(TestAppDbContext db)
        => new(db, PricingFixtures.Publisher(db), new InventoryBatchService(db));

    private static async Task<(TestAppDbContext db, Product monitored, Product plain)> SeedAsync()
    {
        var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        var monitored = PricingFixtures.NewProduct(price: 10m, cost: 5m);
        var plain = PricingFixtures.NewProduct(price: 10m, cost: 5m, monitorExpiry: false);
        db.Products.AddRange(monitored, plain);
        await db.SaveChangesAsync();
        return (db, monitored, plain);
    }

    [Fact]
    public async Task Risk_report_classifies_batches_and_sums_money_at_risk()
    {
        var (db, p, q) = await SeedAsync();
        await using var _ = db;
        db.ProductBatches.AddRange(
            PricingFixtures.NewBatch(p.Id, Today.AddDays(-1), qty: 10, cost: 5),    // expired
            PricingFixtures.NewBatch(p.Id, Today.AddDays(1), qty: 20, cost: 5),     // critical
            PricingFixtures.NewBatch(p.Id, Today.AddDays(10), qty: 30, cost: 5),    // expiring soon
            PricingFixtures.NewBatch(p.Id, Today.AddDays(60), qty: 40, cost: 5),    // normal, excluded
            PricingFixtures.NewBatch(p.Id, Today.AddDays(1), qty: 0, cost: 5),      // empty, excluded
            PricingFixtures.NewBatch(q.Id, Today.AddDays(1), qty: 50, cost: 5));    // not expiry-tracked, excluded
        await db.SaveChangesAsync();

        var report = await Svc(db).GetRiskAsync(null, Today);

        Assert.Equal(new[] { ExpiryStatus.Expired, ExpiryStatus.Critical, ExpiryStatus.ExpiringSoon }, report.Batches.Select(b => b.Status).ToArray());
        Assert.Equal(new[] { -1, 1, 10 }, report.Batches.Select(b => b.DaysLeft).ToArray());
        Assert.Equal(new[] { 50m, 100m, 150m }, report.Batches.Select(b => b.MoneyAtRisk).ToArray());
        var s = Assert.Single(report.Summaries);
        Assert.Equal(250m, s.AtRiskPesos);
        Assert.Equal(50m, s.ExpiredUnwrittenPesos);
        Assert.Equal(0m, s.WrittenOffPesos);
        Assert.Equal(2, s.BatchesAtRisk);
    }

    [Fact]
    public async Task Cost_falls_back_to_the_product_cost_when_the_batch_has_none()
    {
        var (db, p, _) = await SeedAsync();
        await using var __ = db;
        var b = PricingFixtures.NewBatch(p.Id, Today.AddDays(5), qty: 10);
        b.Cost = null;
        db.ProductBatches.Add(b);
        await db.SaveChangesAsync();

        var row = Assert.Single((await Svc(db).GetRiskAsync(null, Today)).Batches);

        Assert.Equal(50m, row.MoneyAtRisk);     // 10 x product cost 5
    }

    [Fact]
    public async Task Branch_filter_limits_the_report()
    {
        var (db, p, _) = await SeedAsync();
        await using var _ = db;
        db.ProductBatches.AddRange(
            PricingFixtures.NewBatch(p.Id, Today.AddDays(1), qty: 10, cost: 5, warehouseId: 1),
            PricingFixtures.NewBatch(p.Id, Today.AddDays(1), qty: 7, cost: 5, warehouseId: 2));
        await db.SaveChangesAsync();

        var report = await Svc(db).GetRiskAsync(new[] { 2 }, Today);

        var row = Assert.Single(report.Batches);
        Assert.Equal(2, row.WarehouseId);
        Assert.Equal(35m, Assert.Single(report.Summaries).AtRiskPesos);
    }

    [Fact]
    public async Task Write_off_zeroes_expired_batches_logs_the_loss_and_fixes_the_cache()
    {
        var (db, p, _) = await SeedAsync();
        await using var _ = db;
        var expired = PricingFixtures.NewBatch(p.Id, Today.AddDays(-1), qty: 10, cost: 5);
        var live = PricingFixtures.NewBatch(p.Id, Today.AddDays(1), qty: 20, cost: 5);
        db.ProductBatches.AddRange(expired, live);
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = p.Id, Quantity = 30 });
        await db.SaveChangesAsync();
        db.ActiveMarkdowns.Add(new ActiveMarkdown { WarehouseId = 1, ProductId = p.Id, BatchId = expired.Id, Price = 8m, IsActive = true, StartsAt = Today.AddDays(-3) });
        await db.SaveChangesAsync();

        var result = await Svc(db).WriteOffExpiredAsync(null, Today.AddHours(6), 9);

        Assert.Equal(1, result.Batches);
        Assert.Equal(10m, result.Units);
        Assert.Equal(50m, result.Pesos);
        Assert.Equal(0m, db.ProductBatches.Single(b => b.Id == expired.Id).QtyOnHand);
        Assert.Equal(20m, db.ProductBatches.Single(b => b.Id == live.Id).QtyOnHand);
        var tx = Assert.Single(db.InventoryTransactions.ToList());
        Assert.Equal(ExpiryTransactionTypes.WriteOff, tx.TransactionType);
        Assert.Equal(10m, tx.QtyOut);
        Assert.Equal(5m, tx.UnitCost);
        Assert.Equal(expired.Id, tx.BatchId);
        Assert.Equal(20m, db.ProductWarehouses.Single().Quantity);     // cache = sum of batches
        Assert.False(db.ActiveMarkdowns.Single().IsActive);
        Assert.Contains(db.BusinessEvents.ToList(), e => e.EventType == BusinessEventTypes.InventoryExpired);
    }

    [Fact]
    public async Task Write_off_is_idempotent_and_waste_shows_in_the_risk_summary()
    {
        var (db, p, _) = await SeedAsync();
        await using var _ = db;
        db.ProductBatches.Add(PricingFixtures.NewBatch(p.Id, Today.AddDays(-2), qty: 10, cost: 5));
        await db.SaveChangesAsync();
        var svc = Svc(db);

        var first = await svc.WriteOffExpiredAsync(null, Today, 9);
        var second = await svc.WriteOffExpiredAsync(null, Today, 9);

        Assert.Equal(50m, first.Pesos);
        Assert.Equal(0, second.Batches);
        Assert.Single(db.InventoryTransactions.ToList());
        var summary = Assert.Single((await svc.GetRiskAsync(null, Today)).Summaries);
        Assert.Equal(50m, summary.WrittenOffPesos);
        Assert.Equal(0m, summary.ExpiredUnwrittenPesos);
    }

    [Fact]
    public async Task Write_off_respects_the_branch_filter()
    {
        var (db, p, _) = await SeedAsync();
        await using var _ = db;
        db.ProductBatches.AddRange(
            PricingFixtures.NewBatch(p.Id, Today.AddDays(-1), qty: 10, cost: 5, warehouseId: 1),
            PricingFixtures.NewBatch(p.Id, Today.AddDays(-1), qty: 4, cost: 5, warehouseId: 2));
        await db.SaveChangesAsync();

        var result = await Svc(db).WriteOffExpiredAsync(new[] { 2 }, Today, 9);

        Assert.Equal(1, result.Batches);
        Assert.Equal(20m, result.Pesos);
        Assert.Equal(10m, db.ProductBatches.Single(b => b.WarehouseId == 1).QtyOnHand);
    }
}
```

- [ ] **Step 2: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter ExpiryServiceTests`
Expected: build FAIL (`ExpiryService` not defined).

- [ ] **Step 3: Implement**

`Services/ExpiryService.cs`:

```csharp
using GoPosify.Data;
using GoPosify.Models;
using GoPosify.Services.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Services;

public static class ExpiryStatus
{
    public const string Normal = "Normal";
    public const string ExpiringSoon = "ExpiringSoon";
    public const string Critical = "Critical";
    public const string Expired = "Expired";
}

public static class ExpiryTransactionTypes
{
    public const string WriteOff = "EXPIRED_WRITE_OFF";
}

public sealed class ExpiryBatchRow
{
    public int WarehouseId { get; set; }
    public int ProductId { get; set; }
    public string ProductName { get; set; }
    public long BatchId { get; set; }
    public string BatchNo { get; set; }
    public DateTime ExpiryDate { get; set; }
    public int DaysLeft { get; set; }
    public decimal QtyOnHand { get; set; }
    public decimal UnitCost { get; set; }
    public decimal MoneyAtRisk { get; set; }
    public string Status { get; set; }
}

public sealed class ExpiryRiskSummary
{
    public int WarehouseId { get; set; }
    public decimal AtRiskPesos { get; set; }            // ExpiringSoon + Critical, still sellable
    public decimal ExpiredUnwrittenPesos { get; set; }  // expired but still sitting in stock
    public decimal WrittenOffPesos { get; set; }        // already written off (waste)
    public int BatchesAtRisk { get; set; }
}

public sealed class ExpiryRiskReport
{
    public List<ExpiryBatchRow> Batches { get; set; } = new();
    public List<ExpiryRiskSummary> Summaries { get; set; } = new();
}

public sealed class WriteOffResult
{
    public int Batches { get; set; }
    public decimal Units { get; set; }
    public decimal Pesos { get; set; }
}

public interface IExpiryService
{
    Task<ExpiryRiskReport> GetRiskAsync(IReadOnlyCollection<int> warehouseIds, DateTime today, int criticalDays = 2);
    Task<WriteOffResult> WriteOffExpiredAsync(IReadOnlyCollection<int> warehouseIds, DateTime now, int? updatedBy);
}

public sealed class ExpiryService : IExpiryService
{
    private readonly AppDBContext _db;
    private readonly IBusinessEventPublisher _events;
    private readonly IInventoryBatchService _batches;

    public ExpiryService(AppDBContext db, IBusinessEventPublisher events, IInventoryBatchService batches)
    {
        _db = db;
        _events = events;
        _batches = batches;
    }

    public async Task<ExpiryRiskReport> GetRiskAsync(IReadOnlyCollection<int> warehouseIds, DateTime today, int criticalDays = 2)
    {
        var ids = warehouseIds?.ToArray();

        var q = _db.ProductBatches.AsNoTracking().Include(b => b.Product)
            .Where(b => b.QtyOnHand > 0 && b.ExpiryDate.HasValue && b.Product.MonitorExpiry);
        if (ids != null) q = q.Where(b => ids.Contains(b.WarehouseId));
        var batches = await q.ToListAsync();

        var rows = new List<ExpiryBatchRow>();
        foreach (var b in batches)
        {
            var days = (b.ExpiryDate.Value.Date - today.Date).Days;
            var alert = b.Product.ExpiryAlertDays > 0 ? b.Product.ExpiryAlertDays : 30;
            var status = days < 0 ? ExpiryStatus.Expired
                : days <= criticalDays ? ExpiryStatus.Critical
                : days <= alert ? ExpiryStatus.ExpiringSoon
                : ExpiryStatus.Normal;
            if (status == ExpiryStatus.Normal)
            {
                continue;
            }

            var cost = b.Cost ?? b.Product.Cost;
            rows.Add(new ExpiryBatchRow
            {
                WarehouseId = b.WarehouseId, ProductId = b.ProductId, ProductName = b.Product.ProductName,
                BatchId = b.Id, BatchNo = b.BatchNo, ExpiryDate = b.ExpiryDate.Value, DaysLeft = days,
                QtyOnHand = b.QtyOnHand, UnitCost = cost, MoneyAtRisk = b.QtyOnHand * cost, Status = status
            });
        }

        rows = rows.OrderBy(r => r.DaysLeft).ThenBy(r => r.BatchId).ToList();

        var wq = _db.InventoryTransactions.AsNoTracking().Where(t => t.TransactionType == ExpiryTransactionTypes.WriteOff);
        if (ids != null) wq = wq.Where(t => ids.Contains(t.WarehouseId));
        var writeOffs = (await wq.Select(t => new { t.WarehouseId, t.QtyOut, t.UnitCost }).ToListAsync())
            .GroupBy(t => t.WarehouseId)
            .ToDictionary(g => g.Key, g => g.Sum(t => t.QtyOut * (t.UnitCost ?? 0m)));

        var warehouseKeys = rows.Select(r => r.WarehouseId).Union(writeOffs.Keys).Distinct().OrderBy(x => x);
        var report = new ExpiryRiskReport { Batches = rows };
        foreach (var wh in warehouseKeys)
        {
            var mine = rows.Where(r => r.WarehouseId == wh).ToList();
            report.Summaries.Add(new ExpiryRiskSummary
            {
                WarehouseId = wh,
                AtRiskPesos = mine.Where(r => r.Status != ExpiryStatus.Expired).Sum(r => r.MoneyAtRisk),
                ExpiredUnwrittenPesos = mine.Where(r => r.Status == ExpiryStatus.Expired).Sum(r => r.MoneyAtRisk),
                WrittenOffPesos = writeOffs.TryGetValue(wh, out var w) ? w : 0m,
                BatchesAtRisk = mine.Count(r => r.Status != ExpiryStatus.Expired)
            });
        }

        return report;
    }

    public async Task<WriteOffResult> WriteOffExpiredAsync(IReadOnlyCollection<int> warehouseIds, DateTime now, int? updatedBy)
    {
        var ids = warehouseIds?.ToArray();
        var today = now.Date;
        var tenantId = _db.CurrentTenantId > 0 ? _db.CurrentTenantId : 1;

        var q = _db.ProductBatches.Include(b => b.Product)
            .Where(b => b.QtyOnHand > 0 && b.ExpiryDate.HasValue && b.ExpiryDate.Value < today && b.Product.MonitorExpiry);
        if (ids != null) q = q.Where(b => ids.Contains(b.WarehouseId));
        var expired = await q.ToListAsync();

        var result = new WriteOffResult();
        if (expired.Count == 0)
        {
            return result;
        }

        var cacheKeys = new HashSet<(int Warehouse, int Product, int? Variant)>();
        foreach (var b in expired)
        {
            var qty = b.QtyOnHand;
            var cost = b.Cost ?? b.Product.Cost;
            b.QtyOnHand = 0m;

            _db.InventoryTransactions.Add(new InventoryTransaction
            {
                TransactionType = ExpiryTransactionTypes.WriteOff,
                ReferenceNo = $"expiry-{today:yyyyMMdd}",
                WarehouseId = b.WarehouseId,
                ProductId = b.ProductId,
                VariantId = b.VariantId,
                BatchId = b.Id,
                QtyIn = 0m,
                QtyOut = qty,
                UnitCost = cost,
                TransactionDate = now,
                UpdatedBy = updatedBy
            });

            _events.Publish(BusinessEventTypes.InventoryExpired, b.WarehouseId, $"expiry-{b.Id}",
                new { batchId = b.Id, productId = b.ProductId, quantity = qty, unitCost = cost, pesos = qty * cost }, now);

            cacheKeys.Add((b.WarehouseId, b.ProductId, b.VariantId));
            result.Batches++;
            result.Units += qty;
            result.Pesos += qty * cost;
        }

        var expiredBatchIds = expired.Select(b => b.Id).ToList();
        var markdowns = await _db.ActiveMarkdowns.Where(m => m.IsActive && expiredBatchIds.Contains(m.BatchId)).ToListAsync();
        foreach (var m in markdowns)
        {
            m.IsActive = false;
            m.EndsAt = now;
        }

        await _db.SaveChangesAsync();

        foreach (var k in cacheKeys)
        {
            await _batches.SyncWarehouseCacheAsync(tenantId, k.Warehouse, k.Product, k.Variant);
        }

        return result;
    }
}
```

- [ ] **Step 4: Register in DI**

In `Program.cs`, after `IMarkdownPricingService`:

```csharp
builder.Services.AddScoped<IExpiryService, ExpiryService>();
```

- [ ] **Step 5: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter ExpiryServiceTests`
Expected: all pass (6 tests). If `Write_off_zeroes_...` fails on the cache assertion, the cause is `SyncWarehouseCacheAsync` using `IgnoreQueryFilters` with the tenant id; confirm `TestAppDbContext` tenant is 5 and `ProductWarehouse` is stamped with tenant 5 on add.

- [ ] **Step 6: Commit**

```bash
git add Services/ExpiryService.cs Program.cs Retailo.Tests/ExpiryServiceTests.cs
git commit -m "feat: expiry risk report and expired-stock write-off through the ledger"
```

---

### Task 6: Pricing and expiry APIs, permissions

**Files (PesoWeb):**
- Create: `DTO/Pricing/PricingDTOs.cs`, `Controllers/PricingController.cs`, `Controllers/ExpiryController.cs`
- Modify: `Helpers/Permissions.cs`
- Generated: migration `GrantPricingPermissionsToOwnerRoles`

**Interfaces:**
- Consumes: `IMarkdownService`, `IExpiryService`, `PricingPolicy`, `PriceChange`, `ActiveMarkdown`.
- Produces HTTP endpoints (JSON bodies; all tenant-scoped by the existing query filter):
  - `GET  api/Pricing/Policy` (`Pricing.View`) returns the policy, or a default view with `autonomyMode: "Off"` and `configured: false`
  - `PUT  api/Pricing/Policy` (`Pricing.Manage`) body `{ hardMarginFloorPct, softMarginFloorPct, maxDiscountPct, maxChangesPerSkuPerHour, autonomyMode }`
  - `POST api/Pricing/Markdown` (`Pricing.Markdown`) body `{ warehouseId, productId, batchId, newPrice, reason, source, predictionRef, endsAt }` returns **200** when applied, **202** when pending approval, **422** when rejected (body is the `MarkdownOutcome`), **400** for invalid references
  - `POST api/Pricing/Approve` (`Pricing.Approve`) body `{ priceChangeId }`; `POST api/Pricing/Reject` body `{ priceChangeId, reason }`
  - `POST api/Pricing/End` (`Pricing.Markdown`) body `{ activeMarkdownId, reason }` returns 200 or 404
  - `GET  api/Pricing/Changes?warehouseId=&status=` and `GET api/Pricing/Active?warehouseId=` (`Pricing.View`)
  - `GET  api/Expiry/Risk?warehouseId=` (`Inventory.ProductList`), `POST api/Expiry/WriteOffExpired?warehouseId=` (`Inventory.StockAdjustmentAdd`). Both are limited to the caller's branches.
- Permissions added: `Pricing.View`, `Pricing.Manage`, `Pricing.Markdown`, `Pricing.Approve`.

- [ ] **Step 1: Add the permissions**

In `Helpers/Permissions.cs`, directly after the `"AI.Read",` line added in Plan 1:

```csharp
                // Pricing
                "Pricing.View", "Pricing.Manage", "Pricing.Markdown", "Pricing.Approve",
```

- [ ] **Step 2: Add the DTOs**

`DTO/Pricing/PricingDTOs.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace GoPosify.DTO.Pricing;

public class PricingPolicyDTO
{
    [Range(0, 1000)] public decimal HardMarginFloorPct { get; set; }
    [Range(0, 1000)] public decimal SoftMarginFloorPct { get; set; }
    [Range(0, 100)] public decimal MaxDiscountPct { get; set; }
    [Range(0, 1000)] public int MaxChangesPerSkuPerHour { get; set; }
    [Required] public string AutonomyMode { get; set; }
}

public class MarkdownRequestDTO
{
    [Required] public int WarehouseId { get; set; }
    [Required] public int ProductId { get; set; }
    [Required] public long BatchId { get; set; }
    public decimal NewPrice { get; set; }
    [StringLength(300)] public string Reason { get; set; }
    public string Source { get; set; }
    [StringLength(64)] public string PredictionRef { get; set; }
    public DateTime? EndsAt { get; set; }
}

public class PriceChangeDecisionDTO
{
    [Required] public long PriceChangeId { get; set; }
    [StringLength(300)] public string Reason { get; set; }
}

public class EndMarkdownDTO
{
    [Required] public long ActiveMarkdownId { get; set; }
    [StringLength(300)] public string Reason { get; set; }
}
```

- [ ] **Step 3: Add the pricing controller**

`Controllers/PricingController.cs`:

```csharp
using System.Security.Claims;
using GoPosify.Data;
using GoPosify.DTO.Pricing;
using GoPosify.Models;
using GoPosify.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Controllers
{
    [Route("api/[controller]/[action]")]
    [ApiController]
    [Authorize]
    public class PricingController : BaseController
    {
        private readonly IMarkdownService _markdowns;

        public PricingController(AppDBContext dbContext, IMarkdownService markdowns) : base(dbContext)
        {
            _markdowns = markdowns;
        }

        private int CurrentUserId() => Convert.ToInt32(User.FindFirstValue(ClaimTypes.Sid));

        // GET: api/pricing/policy
        [HttpGet]
        [Authorize(Policy = "Pricing.View")]
        public async Task<IActionResult> Policy()
        {
            var p = await _dbContext.PricingPolicies.AsNoTracking().FirstOrDefaultAsync();
            if (p == null)
            {
                return Ok(new { configured = false, autonomyMode = AutonomyModes.Off, hardMarginFloorPct = 0, softMarginFloorPct = 0, maxDiscountPct = 0, maxChangesPerSkuPerHour = 0 });
            }

            return Ok(new { configured = true, p.AutonomyMode, p.HardMarginFloorPct, p.SoftMarginFloorPct, p.MaxDiscountPct, p.MaxChangesPerSkuPerHour, p.UpdatedAt });
        }

        // PUT: api/pricing/policy
        [HttpPut]
        [Authorize(Policy = "Pricing.Manage")]
        public async Task<IActionResult> Policy([FromBody] PricingPolicyDTO dto)
        {
            if (!AutonomyModes.All.Contains(dto.AutonomyMode))
            {
                return BadRequest(new { message = $"AutonomyMode must be one of: {string.Join(", ", AutonomyModes.All)}." });
            }

            if (dto.SoftMarginFloorPct < dto.HardMarginFloorPct)
            {
                return BadRequest(new { message = "The soft margin floor must be at or above the hard margin floor." });
            }

            try
            {
                var p = await _dbContext.PricingPolicies.FirstOrDefaultAsync();
                if (p == null)
                {
                    p = new PricingPolicy();
                    _dbContext.PricingPolicies.Add(p);
                }

                p.HardMarginFloorPct = dto.HardMarginFloorPct;
                p.SoftMarginFloorPct = dto.SoftMarginFloorPct;
                p.MaxDiscountPct = dto.MaxDiscountPct;
                p.MaxChangesPerSkuPerHour = dto.MaxChangesPerSkuPerHour;
                p.AutonomyMode = dto.AutonomyMode;
                await _dbContext.SaveChangesAsync();
                return Ok(p);
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while saving the pricing policy.", "Pricing", "Policy");
            }
        }

        // POST: api/pricing/markdown
        [HttpPost]
        [Authorize(Policy = "Pricing.Markdown")]
        public async Task<IActionResult> Markdown([FromBody] MarkdownRequestDTO dto)
        {
            try
            {
                var userId = CurrentUserId();
                if (!await _dbContext.UserWarehouses.AnyAsync(uw => uw.UserId == userId && uw.WarehouseId == dto.WarehouseId))
                {
                    return BadRequest(new { message = "You do not have access to this branch." });
                }

                var source = string.Equals(dto.Source, PriceChangeSource.Ai, StringComparison.OrdinalIgnoreCase)
                    ? PriceChangeSource.Ai : PriceChangeSource.Manual;

                var outcome = await _markdowns.ProposeAsync(new MarkdownProposal
                {
                    WarehouseId = dto.WarehouseId, ProductId = dto.ProductId, BatchId = dto.BatchId, NewPrice = dto.NewPrice,
                    Reason = dto.Reason, PredictionRef = dto.PredictionRef, EndsAt = dto.EndsAt
                }, source, userId, CurrentDateTime());

                if (outcome.Decision == GuardrailDecision.Allowed) return Ok(outcome);
                if (outcome.Decision == GuardrailDecision.NeedsApproval) return StatusCode(StatusCodes.Status202Accepted, outcome);
                return StatusCode(StatusCodes.Status422UnprocessableEntity, outcome);
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while applying the markdown.", "Pricing", "Markdown");
            }
        }

        // POST: api/pricing/approve
        [HttpPost]
        [Authorize(Policy = "Pricing.Approve")]
        public async Task<IActionResult> Approve([FromBody] PriceChangeDecisionDTO dto)
        {
            try
            {
                var outcome = await _markdowns.ApproveAsync(dto.PriceChangeId, CurrentUserId(), CurrentDateTime());
                return outcome.Decision == GuardrailDecision.Allowed ? Ok(outcome) : StatusCode(StatusCodes.Status422UnprocessableEntity, outcome);
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while approving the markdown.", "Pricing", "Approve");
            }
        }

        // POST: api/pricing/reject
        [HttpPost]
        [Authorize(Policy = "Pricing.Approve")]
        public async Task<IActionResult> Reject([FromBody] PriceChangeDecisionDTO dto)
        {
            try
            {
                return Ok(await _markdowns.RejectAsync(dto.PriceChangeId, CurrentUserId(), dto.Reason, CurrentDateTime()));
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while rejecting the markdown.", "Pricing", "Reject");
            }
        }

        // POST: api/pricing/end
        [HttpPost]
        [Authorize(Policy = "Pricing.Markdown")]
        public async Task<IActionResult> End([FromBody] EndMarkdownDTO dto)
        {
            try
            {
                var ended = await _markdowns.EndAsync(dto.ActiveMarkdownId, dto.Reason, CurrentDateTime());
                return ended ? Ok(new { ended = true }) : NotFound(new { message = "No active markdown with that id." });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while ending the markdown.", "Pricing", "End");
            }
        }

        // GET: api/pricing/changes?warehouseId=1&status=Applied
        [HttpGet]
        [Authorize(Policy = "Pricing.View")]
        public async Task<IActionResult> Changes(int? warehouseId, string status)
        {
            var q = _dbContext.PriceChanges.AsNoTracking().AsQueryable();
            if (warehouseId.HasValue) q = q.Where(c => c.WarehouseId == warehouseId.Value);
            if (!string.IsNullOrWhiteSpace(status)) q = q.Where(c => c.Status == status);
            return Ok(await q.OrderByDescending(c => c.Id).Take(500).ToListAsync());
        }

        // GET: api/pricing/active?warehouseId=1
        [HttpGet]
        [Authorize(Policy = "Pricing.View")]
        public async Task<IActionResult> Active(int? warehouseId)
        {
            var q = _dbContext.ActiveMarkdowns.AsNoTracking().Where(m => m.IsActive);
            if (warehouseId.HasValue) q = q.Where(m => m.WarehouseId == warehouseId.Value);
            return Ok(await q.OrderByDescending(m => m.Id).Take(500).ToListAsync());
        }
    }
}
```

- [ ] **Step 4: Add the expiry controller**

`Controllers/ExpiryController.cs`:

```csharp
using System.Security.Claims;
using GoPosify.Data;
using GoPosify.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Controllers
{
    [Route("api/[controller]/[action]")]
    [ApiController]
    [Authorize]
    public class ExpiryController : BaseController
    {
        private readonly IExpiryService _expiry;

        public ExpiryController(AppDBContext dbContext, IExpiryService expiry) : base(dbContext)
        {
            _expiry = expiry;
        }

        // The caller's branches, optionally narrowed to one. Returns null when the requested branch is not theirs.
        private async Task<int[]> ScopeAsync(int? warehouseId)
        {
            var userId = Convert.ToInt32(User.FindFirstValue(ClaimTypes.Sid));
            var mine = await _dbContext.UserWarehouses.Where(uw => uw.UserId == userId).Select(uw => uw.WarehouseId).ToArrayAsync();
            if (!warehouseId.HasValue) return mine;
            return mine.Contains(warehouseId.Value) ? new[] { warehouseId.Value } : null;
        }

        // GET: api/expiry/risk?warehouseId=1
        [HttpGet]
        [Authorize(Policy = "Inventory.ProductList")]
        public async Task<IActionResult> Risk(int? warehouseId)
        {
            var scope = await ScopeAsync(warehouseId);
            if (scope == null) return Forbid();
            return Ok(await _expiry.GetRiskAsync(scope, CurrentDateTime()));
        }

        // POST: api/expiry/writeoffexpired?warehouseId=1
        [HttpPost]
        [Authorize(Policy = "Inventory.StockAdjustmentAdd")]
        public async Task<IActionResult> WriteOffExpired(int? warehouseId)
        {
            try
            {
                var scope = await ScopeAsync(warehouseId);
                if (scope == null) return Forbid();
                var userId = Convert.ToInt32(User.FindFirstValue(ClaimTypes.Sid));
                return Ok(await _expiry.WriteOffExpiredAsync(scope, CurrentDateTime(), userId));
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while writing off expired stock.", "Expiry", "WriteOffExpired");
            }
        }
    }
}
```

- [ ] **Step 5: Build and run all tests**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all tests pass.

- [ ] **Step 6: Grant the new permissions to existing owner roles (migration)**

```bash
dotnet ef migrations add GrantPricingPermissionsToOwnerRoles --project Retailo.csproj
```

The generated migration is empty (no model change). Replace its `Up` and `Down` bodies with the following. This also grants the Plan 1 `Cash.*` and `AI.Read` permissions to every tenant's `SuperAdmin` role (Plan 1 only granted the root role), so existing tenants can use them. New tenants already get every permission at registration.

```csharp
        private static readonly string[] Permissions =
        {
            "Cash.Shift", "Cash.ShiftList", "AI.Read",
            "Pricing.View", "Pricing.Manage", "Pricing.Markdown", "Pricing.Approve"
        };

        protected override void Up(MigrationBuilder migrationBuilder)
        {
            foreach (var p in Permissions)
            {
                migrationBuilder.Sql(
                    $"UPDATE Roles SET Permissions = Permissions + ',{p}' " +
                    $"WHERE Title = 'SuperAdmin' AND (',' + Permissions + ',') NOT LIKE '%,{p},%';");
            }
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            foreach (var p in Permissions)
            {
                migrationBuilder.Sql($"UPDATE Roles SET Permissions = REPLACE(Permissions, ',{p}', '') WHERE Title = 'SuperAdmin';");
            }
        }
```

- [ ] **Step 7: Apply, verify routes and commit**

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
```

Start the app (`dotnet run --project Retailo.csproj --urls http://localhost:5061`) and confirm the routes exist:

Run: `powershell -Command "(Invoke-RestMethod http://localhost:5061/swagger/v1/swagger.json).paths.PSObject.Properties.Name | Where-Object { $_ -match 'api/(Pricing|Expiry)' }"`
Expected: `/api/Pricing/Policy`, `/api/Pricing/Markdown`, `/api/Pricing/Approve`, `/api/Pricing/Reject`, `/api/Pricing/End`, `/api/Pricing/Changes`, `/api/Pricing/Active`, `/api/Expiry/Risk`, `/api/Expiry/WriteOffExpired`.

```bash
git add DTO/Pricing/PricingDTOs.cs Controllers/PricingController.cs Controllers/ExpiryController.cs Helpers/Permissions.cs Migrations/*GrantPricingPermissionsToOwnerRoles*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: pricing and expiry APIs, permissions, grant to owner roles"
```

---

### Task 7: AI read endpoints for expiry risk, price changes and active markdowns

**Files (PesoWeb):**
- Modify: `Controllers/AiController.cs`

**Interfaces:**
- Consumes: `IExpiryService`, `PriceChange`, `ActiveMarkdown`, the `AI.Read` permission from Plan 1.
- Produces (all `GET`, `AI.Read`, tenant-wide, read-only):
  - `api/ai/expiry-risk?warehouseId=` returns `ExpiryRiskReport`
  - `api/ai/price-changes?afterId=0&take=500` returns `{ changes: [...], nextAfterId }` ordered by id ascending (cursor style, like events)
  - `api/ai/active-markdowns?warehouseId=` returns the active `ActiveMarkdown` rows

- [ ] **Step 1: Inject the expiry service**

In `Controllers/AiController.cs`, replace:

```csharp
        private readonly ILedgerService _ledger;

        public AiController(AppDBContext dbContext, ILedgerService ledger) : base(dbContext)
        {
            _ledger = ledger;
        }
```

with:

```csharp
        private readonly ILedgerService _ledger;
        private readonly IExpiryService _expiry;

        public AiController(AppDBContext dbContext, ILedgerService ledger, IExpiryService expiry) : base(dbContext)
        {
            _ledger = ledger;
            _expiry = expiry;
        }
```

- [ ] **Step 2: Add the three actions**

Directly after the `LedgerDrift` action (after its closing brace, anchored on `return Ok(await _ledger.GetDriftAsync(warehouseId, tolerance));`):

```csharp
        // GET: api/ai/expiry-risk?warehouseId=1
        [HttpGet("~/api/ai/expiry-risk")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> ExpiryRisk(int? warehouseId)
        {
            var scope = warehouseId.HasValue ? new[] { warehouseId.Value } : null;
            return Ok(await _expiry.GetRiskAsync(scope, CurrentDateTime()));
        }

        // GET: api/ai/price-changes?afterId=0&take=500
        [HttpGet("~/api/ai/price-changes")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> PriceChanges(long afterId = 0, int take = 500)
        {
            take = Math.Clamp(take, 1, 1000);
            var rows = await _dbContext.PriceChanges.AsNoTracking()
                .Where(c => c.Id > afterId).OrderBy(c => c.Id).Take(take).ToListAsync();
            return Ok(new { changes = rows, nextAfterId = rows.Count > 0 ? rows[^1].Id : afterId });
        }

        // GET: api/ai/active-markdowns?warehouseId=1
        [HttpGet("~/api/ai/active-markdowns")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> ActiveMarkdowns(int? warehouseId)
        {
            var q = _dbContext.ActiveMarkdowns.AsNoTracking().Where(m => m.IsActive);
            if (warehouseId.HasValue) q = q.Where(m => m.WarehouseId == warehouseId.Value);
            return Ok(await q.OrderBy(m => m.Id).Take(2000).ToListAsync());
        }
```

- [ ] **Step 3: Build, test, verify routes**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all tests pass.

Start the app and run: `powershell -Command "(Invoke-RestMethod http://localhost:5061/swagger/v1/swagger.json).paths.PSObject.Properties.Name | Where-Object { $_ -match 'api/ai' }"`
Expected: Plan 1's three paths plus `/api/ai/expiry-risk`, `/api/ai/price-changes`, `/api/ai/active-markdowns`.

- [ ] **Step 4: Commit**

```bash
git add Controllers/AiController.cs
git commit -m "feat: AI read endpoints for expiry risk, price changes, and active markdowns"
```

---

### Task 8: End-to-end smoke through the real API (guardrails, markdown at the POS, events)

**Files (hackathon repo):**
- Create: `pesoweb-additions/smoke/pricing-smoke.ps1`

**Interfaces:**
- Consumes: `New-` and `Invoke-PesoApi` helpers from `pesoweb-additions/smoke/common.ps1` (Plan 1 Task 3), and every endpoint from Tasks 6 and 7.
- Needs a **dev tenant owner** login that already has at least one expiry-tracked batch with stock. Credentials come from the environment variables `PESOWEB_EMAIL` and `PESOWEB_PASSWORD`; nothing is stored in the repo. The tenant's `SuperAdmin` role must have the new permissions (Task 6 Step 6 grants them).
- Side effects (the script refuses to run without `-Yes`): sets the tenant's pricing policy, creates one markdown, ends it, creates **two real sales** of 1 unit each, writes events. Use a DEV tenant only.
- If the dev database has no expiry batch, receive one first with the FEFO checklist (`D:\git\Retailo_v1\scripts\fefo_smoke_test_checklist.md`).

- [ ] **Step 1: Write the script**

`pesoweb-additions/smoke/pricing-smoke.ps1`:

```powershell
param(
    [string] $BaseUrl = 'http://localhost:5061',
    [string] $Email = $env:PESOWEB_EMAIL,
    [string] $Password = $env:PESOWEB_PASSWORD,
    [switch] $Yes
)
. "$PSScriptRoot\common.ps1"

if (-not $Email -or -not $Password) { throw 'Set PESOWEB_EMAIL and PESOWEB_PASSWORD to a DEV tenant owner. Nothing is stored in the repo.' }
if (-not $Yes) { throw 'This script sets a pricing policy, creates a markdown and two real sales on the tenant you log in to. Re-run with -Yes on a DEV tenant.' }

# Raw HTTP helper that returns the status code (Invoke-RestMethod hides 202/422 details in PowerShell 5.1)
function Invoke-PesoStatus {
    param([string] $Method, [string] $Path, $Body, [string] $Token, [string] $SimRun)
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        $json = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 6 -Compress } else { '' }
        [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding $false))
        $args = @('-s', '-X', $Method, "$BaseUrl$Path", '-H', "Authorization: Bearer $Token", '-H', 'Content-Type: application/json', '-w', "`n%{http_code}")
        if ($SimRun) { $args += @('-H', "X-Sim-Run: $SimRun") }
        if ($null -ne $Body) { $args += @('--data-binary', "@$tmp") }
        $raw = & curl.exe @args
        $lines = @($raw)
        $status = [int]$lines[-1]
        $text = ($lines[0..($lines.Count - 2)] -join "`n")
        $parsed = if ($text) { try { $text | ConvertFrom-Json } catch { $text } } else { $null }
        return [pscustomobject]@{ Status = $status; Body = $parsed }
    } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

function Assert-True($cond, $what) { if (-not $cond) { throw "FAIL $what" } ; Write-Host "OK   $what" }

$run = 'pricing-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8)

# 1. Login
$login = Invoke-PesoApi -BaseUrl $BaseUrl -Method POST -Path '/api/Auth/Login' -Body @{ Email = $Email; Password = $Password; IsRemember = $false }
$t = $login.token; $wh = $login.defaultWarehouseId
Assert-True ($t -and $wh) "logged in, default branch $wh"

# 2. Policy: autonomous within guardrails
$pol = Invoke-PesoStatus PUT '/api/Pricing/Policy' @{ hardMarginFloorPct = 5; softMarginFloorPct = 15; maxDiscountPct = 50; maxChangesPerSkuPerHour = 3; autonomyMode = 'Autonomous' } $t
Assert-True ($pol.Status -eq 200) 'policy saved (200)'

# 3. Find an expiry-tracked batch with stock
$ne = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Inventory/NearExpiryBatches?warehouse=$wh&pageSize=50"
$batch = @($ne.data | Where-Object { $_.qtyOnHand -gt 0 }) | Select-Object -First 1
if (-not $batch) { throw 'No near-expiry batch with stock in this branch. Receive one first (see scripts/fefo_smoke_test_checklist.md).' }
Write-Host "Using batch $($batch.id) product $($batch.productId) qty $($batch.qtyOnHand) cost $($batch.cost) expires $($batch.expiryDate)"

# 4. Product list price
$pd = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Inventory/ProductDetail?id=$($batch.productId)&warehouse=$wh"
$price = if ($pd.price) { [decimal]$pd.price } elseif ($pd.product.price) { [decimal]$pd.product.price } else { 0 }
if ($price -le 0) { $pd | ConvertTo-Json -Depth 3; throw 'Could not read the product price from ProductDetail; adjust the property name in this script.' }
Write-Host "List price $price"

# 5. Guardrail: an absurd markdown must be refused (422) and recorded
$bad = Invoke-PesoStatus POST '/api/Pricing/Markdown' @{ warehouseId = $wh; productId = $batch.productId; batchId = $batch.id; newPrice = 0.01; reason = 'smoke: absurd'; source = 'Ai' } $t $run
Assert-True ($bad.Status -eq 422) "absurd markdown refused (422, code $($bad.Body.code))"

# 6. A sensible markdown (20% off) is applied, or waits for approval if it is under the soft floor
$newPrice = [math]::Round($price * 0.8, 2)
$m = Invoke-PesoStatus POST '/api/Pricing/Markdown' @{ warehouseId = $wh; productId = $batch.productId; batchId = $batch.id; newPrice = $newPrice; reason = 'smoke: 20% off'; source = 'Ai'; predictionRef = 'smoke-pred-1' } $t $run
if ($m.Status -eq 202) {
    Write-Host 'Needs approval (soft floor). Approving.'
    $a = Invoke-PesoStatus POST '/api/Pricing/Approve' @{ priceChangeId = $m.Body.priceChangeId } $t $run
    Assert-True ($a.Status -eq 200) 'approved (200)'
    $activeId = $a.Body.activeMarkdownId
} elseif ($m.Status -eq 200) {
    $activeId = $m.Body.activeMarkdownId
} else {
    throw "Markdown refused with $($m.Status) code $($m.Body.code): $($m.Body.message). Check the product's cost and price; the markdown must be a real discount above the hard floor."
}
Assert-True ($activeId -gt 0) "markdown active (id $activeId)"

$active = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Pricing/Active?warehouseId=$wh"
Assert-True (@($active | Where-Object { $_.id -eq $activeId }).Count -eq 1) 'markdown listed in /api/Pricing/Active'

# 7. A real sale of 1 unit consumes FEFO and should be priced from the markdown
$cust = (Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path '/api/People/Customers?page=1&pageSize=5').data | Select-Object -First 1
if (-not $cust) { throw 'No customer found for the sale.' }
function New-SmokeSale([string] $label) {
    $out = & curl.exe -s -w "`n%{http_code}" -X POST "$BaseUrl/api/Sales/AddSale" -H "Authorization: Bearer $t" -H "X-Sim-Run: $run" `
        -F "warehouseId=$wh" -F "customerId=$($cust.id)" -F 'discountPercentage=0' -F 'taxPercentage=0' -F 'shippingCharges=0' `
        -F 'paidAmount=100000' -F 'paymentMethod=Cash' -F 'orderStatus=1' `
        -F "saleDetails[0].productId=$($batch.productId)" -F 'saleDetails[0].quantity=1'
    $lines = @($out); $status = [int]$lines[-1]
    if ($status -ne 201) { throw "AddSale ($label) returned $status : $($lines[0..($lines.Count - 2)] -join ' ')" }
    return ($lines[0..($lines.Count - 2)] -join "`n") | ConvertFrom-Json
}
$saleMd = New-SmokeSale 'markdown'
$mdUnit = [decimal]$saleMd.saleDetails[0].salePrice
Write-Host "Sale 1 unit price (markdown active): $mdUnit"

# 8. End the markdown; the next sale returns to the normal price
$end = Invoke-PesoStatus POST '/api/Pricing/End' @{ activeMarkdownId = $activeId; reason = 'smoke: end' } $t $run
Assert-True ($end.Status -eq 200) 'markdown ended (200)'
$saleNormal = New-SmokeSale 'normal'
$normalUnit = [decimal]$saleNormal.saleDetails[0].salePrice
Write-Host "Sale 2 unit price (no markdown): $normalUnit"
Assert-True ($mdUnit -lt $normalUnit) "markdown sale cheaper than normal ($mdUnit < $normalUnit)"

# 9. Events: two PriceChanged (markdown + restore) and two SaleCompleted, all tagged with this run
$ev = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/ai/events?simRunId=$run&take=1000"
$types = @($ev.events | ForEach-Object { $_.eventType })
Assert-True (@($types | Where-Object { $_ -eq 'PriceChanged' }).Count -ge 2) 'PriceChanged events published (markdown + restore)'
Assert-True (@($types | Where-Object { $_ -eq 'SaleCompleted' }).Count -eq 2) 'SaleCompleted events published'

# 10. Ledger and read APIs
$pc = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Pricing/Changes?warehouseId=$wh"
$statuses = @($pc | ForEach-Object { $_.status })
Assert-True ($statuses -contains 'Rejected') 'ledger recorded the refused markdown'
Assert-True ($statuses -contains 'Ended') 'ledger recorded the restore'
$risk = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/Expiry/Risk?warehouseId=$wh"
Write-Host ("Expiry risk summaries: " + ($risk.summaries | ConvertTo-Json -Compress))
$aiRisk = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path "/api/ai/expiry-risk?warehouseId=$wh"
Assert-True ($null -ne $aiRisk.batches) '/api/ai/expiry-risk answers'
$chg = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t -Method GET -Path '/api/ai/price-changes?afterId=0&take=50'
Assert-True (@($chg.changes).Count -ge 3) '/api/ai/price-changes answers'

Write-Host 'ALL CHECKS PASSED'
```

- [ ] **Step 2: Run it against the running app**

Start PesoWeb (same command as Plan 1), then:

```powershell
$env:PESOWEB_EMAIL = '<dev tenant owner email>'
$env:PESOWEB_PASSWORD = '<its password>'
powershell -File pesoweb-additions/smoke/pricing-smoke.ps1 -Yes
```

Expected: every line starts with `OK` and the last line is `ALL CHECKS PASSED`.

If a check fails, fix PesoWeb (not the script) unless the script is wrong. Likely script-side adjustments: the `ProductDetail` property name for price (the script prints the object and stops), or the `Customers` response shape. A `403` on `Pricing/...` or `ai/...` means the role lacks the permission: confirm the Task 6 Step 6 migration ran against this database and that the role's title is `SuperAdmin`.
**The sale step is the highest-risk check in this plan** (it exercises the `AddSale` hook). If `mdUnit` is not lower than `normalUnit`, verify with `scripts/fefo_integrity_checks.sql` that the sale consumed from the marked batch (FEFO consumes the earliest-expiry batch first, and the script marks the earliest near-expiry batch returned by `NearExpiryBatches`, which is ordered by expiry).

- [ ] **Step 3: Commit**

```bash
cd /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas
git add pesoweb-additions/smoke/pricing-smoke.ps1
git commit -m "P2: pricing smoke through the real API"
```

---

### Task 9: Ship Plan 2 (production script, patches, spec notes)

**Files:**
- Create (PesoWeb): `scripts/20261004_markdown_core.sql`
- Create (hackathon repo): `pesoweb-additions/patches/plan2/*.patch`
- Modify (hackathon repo): `pesoweb-additions/README.md`, `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md`

- [ ] **Step 1: Run the full unit suite**

Run (PesoWeb repo): `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: all pass: Plan 1's 23 plus Plan 2's new tests (guardrails 16, markdown service 13, pricing service 11, expiry 6 = 46), 69 in total.

- [ ] **Step 2: Generate the idempotent production script**

```bash
cd /d/git/Retailo_v1
dotnet ef migrations script --idempotent --project Retailo.csproj -o scripts/20261004_markdown_core.sql
```

Open it and confirm the three Plan 2 migrations (`AddPricingPolicy`, `AddPriceLedgerAndMarkdowns`, `GrantPricingPermissionsToOwnerRoles`) appear inside `__EFMigrationsHistory` guards. Plan 1's migrations will also appear as guarded no-ops; that is expected.

```bash
git add scripts/20261004_markdown_core.sql
git commit -m "chore: idempotent deployment script for markdown core migrations"
```

- [ ] **Step 3: Export the Plan 2 patches**

```bash
cd /d/git/Retailo_v1
mkdir -p /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches/plan2
git format-patch plan1-complete..Retail_MissionCommerceAI -o /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches/plan2
ls /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches/plan2
```

Expected: one `.patch` per Plan 2 commit (about 9). Review for secrets: `grep -il "password\|secret\|connectionstring" pesoweb-additions/patches/plan2/*.patch` should list only files where the match is a test fixture, never a real credential. If a real credential appears, stop and report.

- [ ] **Step 4: Update the patch README**

Append to `pesoweb-additions/README.md`:

```markdown

## Plan 2: expiry risk and agentic markdown core
Apply after the Plan 1 patches:

    git am pesoweb-additions/patches/plan2/*.patch
    dotnet test Retailo.Tests/Retailo.Tests.csproj
    dotnet ef database update            # local/dev database
    # production: run scripts/20261004_markdown_core.sql (idempotent)

Adds: per-tenant pricing policy and guardrails (`/api/Pricing/*`), price-change ledger, per-batch markdowns applied at the POS in `AddSale`,
`PriceChanged` events, expiry risk report and expired-stock write-off (`/api/Expiry/*`), and read endpoints
`/api/ai/expiry-risk`, `/api/ai/price-changes`, `/api/ai/active-markdowns`.

Smoke (DEV tenant only, creates two real sales):

    $env:PESOWEB_EMAIL='...'; $env:PESOWEB_PASSWORD='...'
    powershell -File pesoweb-additions/smoke/pricing-smoke.ps1 -Yes
```

- [ ] **Step 5: Record the spec notes**

In `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md`, directly under the Plan 1 "Implementation notes", add:

```markdown
**Implementation notes (Plan 2):**
- Markdowns are per batch and applied inside `AddSale` after FEFO consumption, so a line that spans a marked-down batch and a fresh batch gets the quantity-weighted price. Markdowns apply to non-variant products only in this plan.
- All guardrail checks use the net price (list price after the product's own discount percent, before tax). The hard margin floor, the maximum discount and the change-rate limit can never be waived; only the soft floor and approval mode can be approved by a person. Hard limits are re-checked at sale time, and autonomy `Off` is a kill switch for existing markdowns.
- The per-branch waste target is not stored or enforced in PesoWeb in this plan. It stays an objective input for the AI optimizer (Plan 5).
- PesoWeb had no expired-stock write-off. Plan 2 adds one that logs `EXPIRED_WRITE_OFF` rows (quantity out at unit cost) to `InventoryTransactions`, so waste in pesos is measured from the ledger and the ledger-drift check stays consistent.
- The new `Pricing.*`, `AI.Read` and `Cash.*` permissions are granted to every tenant's `SuperAdmin` role by migration; new tenants receive them at registration.
```

- [ ] **Step 6: Commit in the hackathon repo**

```bash
cd /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas
git add pesoweb-additions/README.md pesoweb-additions/patches/plan2 Docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md
git commit -m "P2: markdown core patches, README and spec implementation notes"
```

---

## Exit criteria for Plan 2

- 69 xUnit tests pass; `pricing-smoke.ps1` prints `ALL CHECKS PASSED` against a dev tenant.
- A tenant owner can set a pricing policy; a markdown below the hard floor, above the maximum discount, or when autonomy is off is refused with a code and recorded in the ledger; a markdown between the floors waits for approval; a valid markdown is applied.
- A sale through the real `AddSale` prices the units taken from a marked-down batch at the markdown price and other units at the normal price; ending the markdown restores the normal price.
- Every applied or ended markdown emits a `PriceChanged` event tagged with `X-Sim-Run`, readable through `/api/ai/events`.
- Expired stock can be written off, the loss appears as waste in pesos in the expiry risk summary, and the warehouse cache stays equal to the sum of batches.
- Patches and the idempotent SQL script exist and contain no secrets.

## Self-review (against the spec)

**Spec coverage.**
- Item 5 expiry money-at-risk and the flagged "how are expired batches written off" question: Task 5 (finding: no write-off existed; added through the ledger).
- Item 12 pricing guardrails (hard and soft floors, maximum discount, change rate, autonomy mode, enforced inside PesoWeb): Tasks 1 and 3, re-checked at sale time in Task 4.
- Item 10 price-change ledger: Tasks 2 and 3.
- Item 11 markdowns applied at the POS: Task 4.
- Item 13 `PriceChanged` events on the outbox: Tasks 2 and 3 (simulated channel sinks and their lag are Sim work in Plan 4).
- Expiry monitoring by branch and money at risk: Tasks 5, 6, 7.
- Not in this plan: item 9 (corporate group link, Enterprise tier row), items 2, 4, 6, 7. They are Plan 3, as listed in the series table.
- The spec's per-branch waste target as a stored guardrail was intentionally dropped from enforcement and recorded in the spec notes (Task 9 Step 5).

**Placeholder scan.** No TBD/TODO. Two steps are investigative by nature and say so with exact acceptance criteria: Task 8 Step 2 (script-side property-name adjustments for `ProductDetail` and `Customers`) and the `AddSale` block uniqueness check in Task 4 Step 6.

**Type consistency.** Names used identically across tests, services, controllers and the smoke script: `PricingPolicy`, `AutonomyModes`, `GuardrailDecision`, `GuardrailCodes`, `GuardrailResult`, `MarkdownGuardrails.NetPrice/HardViolation/HardLimitsHold/Evaluate`, `PriceChange`, `PriceChangeStatus`, `PriceChangeSource`, `ActiveMarkdown`, `MarkdownProposal`, `MarkdownOutcome`, `IMarkdownService` (Propose/Approve/Reject/End), `IMarkdownPricingService.EffectiveBasePriceAsync`, `IExpiryService.GetRiskAsync/WriteOffExpiredAsync`, `ExpiryStatus`, `ExpiryTransactionTypes.WriteOff`, `BusinessEventTypes.PriceChanged/InventoryExpired`, `PricingFixtures`. `MarkdownProposal.NewPrice` and `ActiveMarkdown.Price` are base prices (the unit of `Product.Price`); guardrail inputs are net prices.

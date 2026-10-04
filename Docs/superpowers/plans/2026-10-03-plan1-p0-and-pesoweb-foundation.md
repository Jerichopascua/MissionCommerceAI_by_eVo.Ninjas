# Plan 1: P0 Setup + PesoWeb Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the AMD stack works, and make PesoWeb "simulation-ready" with a cashier shift and cash-variance model, a business event outbox with a read API for the simulator, and an inventory ledger drift check.

**Architecture:** All PesoWeb changes are additive (new tables, new services, new controllers, nullable columns) in the existing ASP.NET Core 9 / EF Core 7 / SQL Server app at `D:\git\Retailo_v1`, on a dedicated branch. Business logic lives in small services with an in-memory-DB xUnit test project; controllers are thin. The Sim service (Plan 3) will drive these through the real HTTP APIs.

**Tech Stack:** ASP.NET Core (net9.0), EF Core 7.0.13, SQL Server, xUnit + EF Core InMemory (tests), PowerShell (API smoke scripts), Python 3 + PyTorch/ROCm + vLLM (AMD smoke only).

**Spec:** `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md` (this repo). Problem statement: `Docs/problem-statement.md`.

## Plan series (this is plan 1 of 5)

| Plan | Scope | Status |
|---|---|---|
| **1 (this)** | P0 AMD smoke; PesoWeb items 1 (cash shift), 8 (event outbox + read API), 3 (ledger drift, audit columns) | write now |
| 2 | PesoWeb items 4 (stock count), 5 (expiry money-at-risk), 6 (receiving discrepancy), 7 (Exception Center), 2 (sale lifecycle events) | after plan 1 is built |
| 3 | Sim core: world, owners, verticals, behavior, driver, Day-to-Day, incident ledger and scoring | after plan 2 |
| 4 | AI on AMD: forecast, mission detection, anomaly detectors, vLLM investigator, Kuya Pedro wiring | after plan 3 |
| 5 | Scenario Sim, Quick Sim lane, UI, Week 0 vs Week 3, packaging, demo | after plan 4 |

## Execution log and corrections (2026-10-05)

Executed inline in a **git worktree** `D:\git\Retailo_v1_mission` on branch `Retail_MissionCommerceAI` (the user's folder `D:\git\Retailo_v1` stays on `main` with its own uncommitted work). Paths in this plan that say `D:\git\Retailo_v1` mean the worktree.

| Task | Status |
|---|---|
| 1 AMD smoke | Scripts and guide written and tested locally; **run by the user on the AMD server** |
| 2 Harness | Done (commit `91a4331`) |
| 3 Onboarding contract | **Blocked: SQL Server Express was stopped.** Script written (`onboarding-contract.ps1`), not run |
| 4-9 Outbox, cash tables, cash service, cash API, ledger drift, AI API | Done, 23 tests passing |
| 10 Smoke, SQL script, patches | SQL script and patches done; `cash-shift-smoke.ps1` written and syntax-checked, **not run** |

Corrections found while executing (the steps below were wrong or incomplete as originally written):
1. **Task 2:** the main `Retailo.csproj` must exclude the test folder from `Compile`, `None`, `Content` **and** `EmbeddedResource`. The `Compile Remove` line seen earlier was an *uncommitted* change in the user's folder, and without `Content Remove` the Web SDK's `**/*.json` glob copies `Retailo.Tests/bin` into itself recursively.
2. **Task 2:** the in-memory database enforces `[Required]`, so test entities need their required strings (`Warehouse`: Address, Email, Phone; `Product`: ProductCode, BarcodeType, ProductName).
3. **All migrations:** `dotnet ef migrations add` always emits ~44 `UpdateData` statements that rewrite seed rows (the model's seed data uses `DateTime.UtcNow`; one of them touches user 1's `LastLogin`). Strip them with `pesoweb-additions/tools/strip_seed_noise.py <migration.cs>` and confirm only the intended tables/columns remain. The plan's "stop and report" guard is replaced by "strip, then verify".
4. **Task 7:** `SalesController` has no `using GoPosify.Services;`; it must be added.
5. **Task 7 migration:** `GrantCashAndAiPermissionsToOwnerRoles` grants `Cash.Shift`, `Cash.ShiftList` and `AI.Read` to **every tenant's `SuperAdmin` role** (not only role 1), per the owner's decision that the central company's subsidiaries use `SuperAdmin`.
6. `dotnet ef migrations add ... --no-build` after a build is the fast path; `migrations add` does not need the database.

## Global Constraints

- PesoWeb changes are **additive only**: new tables, services, controllers, nullable columns. No behaviour change to existing endpoints except the two marked hooks in `SalesController.AddSale` (Task 7).
- Every new table that holds tenant data has an `int TenantID` property (PesoWeb auto-applies the tenant query filter and stamps `TenantID` on add for any entity that has it).
- Controllers follow PesoWeb conventions: `[Route("api/[controller]/[action]")]`, `[Authorize(Policy = "...")]`, derive from `BaseController`, user id from `ClaimTypes.Sid`, username from `ClaimTypes.NameIdentifier`, time from `CurrentDateTime()` (tenant local wall-clock).
- New permission strings go in `Helpers/Permissions.cs` `GetAllPermissions()`; policies are auto-registered from that list; new tenants get all of them at registration.
- Simulator traffic is tagged with the HTTP header `X-Sim-Run` (max 64 chars kept).
- Cash wording in any user-visible text: "variance" / "unexplained variance", never "theft".
- PesoWeb work happens on branch `Retail_MissionCommerceAI` of `D:\git\Retailo_v1` (base branch `main`). That repo has **unrelated uncommitted changes**; never `git add .` or `git add -A` there. Add explicit file paths only.
- No secrets in git. Use environment variables.
- Migrations are applied to the **local dev database only**. Production gets an idempotent script (Task 10).
- Tests: xUnit, `Retailo.Tests` project inside `D:\git\Retailo_v1` (the main csproj already excludes `Retailo.Tests\**` from its compile).

---

## File structure

**Hackathon repo** (`d:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas`)
- `ai/smoke/rocm_check.py`: GPU and ROCm check with a timed matmul
- `ai/smoke/llm_smoke.py`: calls an OpenAI-compatible vLLM endpoint
- `Docs/amd-smoke-test.md`: recorded results of the AMD smoke test
- `pesoweb-additions/smoke/common.ps1`: PowerShell helpers (register, login, API call)
- `pesoweb-additions/smoke/onboarding-contract.ps1`: proves Register, Login, AddWarehouse and lists API routes
- `pesoweb-additions/smoke/cash-shift-smoke.ps1`: end-to-end shift, events and variance check
- `pesoweb-additions/README.md`: how to apply the exported patch
- `pesoweb-additions/patches/*.patch`: exported PesoWeb commits (Task 10)
- `Docs/onboarding-contract.md`: verified signup-to-catalog chain

**PesoWeb repo** (`D:\git\Retailo_v1`), all new files unless marked
- `Retailo.Tests/Retailo.Tests.csproj`, `Retailo.Tests/Support/TestAppDbContext.cs`, `Retailo.Tests/HarnessTests.cs`
- `Models/BusinessEvent.cs`; `Services/BusinessEventPublisher.cs` (interface, constants, implementation)
- `Models/CashShift.cs` (CashShift, CashMovement); modify `Models/Sale.cs`, `Models/AuditLog.cs`
- `Services/CashShiftService.cs` (calculator, status/type constants, summary, interface, implementation)
- `DTO/CashShifts/CashShiftDTOs.cs`; `Controllers/CashShiftsController.cs`
- `Services/LedgerService.cs`
- `Controllers/AiController.cs`
- modify `Data/AppDBContext.cs` (DbSets), `Program.cs` (DI), `Helpers/Permissions.cs`, `Controllers/SalesController.cs`
- tests: `Retailo.Tests/BusinessEventPublisherTests.cs`, `CashShiftServiceTests.cs`, `LedgerServiceTests.cs`
- migrations (generated): `AddBusinessEvents`, `AddCashShiftsAndAuditContext`, `GrantCashPermissionsToDefaultRole`

---

### Task 1: AMD environment smoke test (P0)

**Files:**
- Create: `ai/smoke/rocm_check.py`
- Create: `ai/smoke/llm_smoke.py`
- Create: `Docs/amd-smoke-test.md`

**Interfaces:**
- Produces: a recorded, reproducible proof that (a) PyTorch sees an AMD GPU via ROCm and (b) a vLLM endpoint answers. Later plans reuse the env vars `VLLM_BASE_URL` and `VLLM_MODEL`.

- [ ] **Step 1: Get access**

Join the AMD AI Developer Program (ADP) and claim the new-member credit, then launch a GPU instance on AMD Developer Cloud using the ROCm + PyTorch image/template the cloud console lists. Record in `Docs/amd-smoke-test.md`: date, instance type, GPU name, image used. (No API keys or tokens in this file.)

- [ ] **Step 2: Write the ROCm check**

```python
# ai/smoke/rocm_check.py
import time
import torch


def main() -> None:
    print("torch:", torch.__version__)
    print("hip:", getattr(torch.version, "hip", None))
    assert torch.cuda.is_available(), "No GPU visible to PyTorch (ROCm build expected)"
    print("device:", torch.cuda.get_device_name(0))
    n = 8192
    a = torch.randn(n, n, device="cuda", dtype=torch.float16)
    b = torch.randn(n, n, device="cuda", dtype=torch.float16)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(10):
        a @ b
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    tflops = 10 * 2 * n**3 / dt / 1e12
    print(f"matmul fp16 {n}x{n} x10: {dt:.3f}s  ~{tflops:.1f} TFLOPS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it on the AMD instance**

Run: `python ai/smoke/rocm_check.py`
Expected: prints a non-null `hip` version, an AMD device name, and a TFLOPS figure. If `torch.cuda.is_available()` is False, you are on a CPU build; reinstall the ROCm wheel from the template and rerun.

- [ ] **Step 4: Write the vLLM smoke client**

```python
# ai/smoke/llm_smoke.py
import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # starting default; swap to any model that fits the GPU


def main() -> None:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "In one sentence: why does a retail cash drawer end the day short?"}],
        "max_tokens": 80,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    dt = time.perf_counter() - t0
    text = out["choices"][0]["message"]["content"]
    toks = out.get("usage", {}).get("completion_tokens", 0)
    print("reply:", text)
    print(f"latency {dt:.2f}s, completion_tokens {toks}, ~{toks / dt:.1f} tok/s")
    assert text.strip(), "empty completion"


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Serve a model and run the client**

On the AMD instance, start vLLM (ROCm build, from the template) serving the model in `VLLM_MODEL`, for example: `vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000`. In a second shell run `python ai/smoke/llm_smoke.py`.
Expected: a one-sentence reply and a tok/s figure. In a third shell run `rocm-smi` while the request runs and note GPU utilization.

- [ ] **Step 6: Record results and commit**

Fill `Docs/amd-smoke-test.md` with: instance/GPU, `rocm_check.py` output, model used, `llm_smoke.py` output, and a `rocm-smi` snapshot. If anything failed, record what failed and the workaround.

```bash
git add ai/smoke/rocm_check.py ai/smoke/llm_smoke.py Docs/amd-smoke-test.md
git commit -m "P0: AMD ROCm and vLLM smoke test"
```

---

### Task 2: PesoWeb branch and test harness

**Files (in `D:\git\Retailo_v1`):**
- Create: `Retailo.Tests/Retailo.Tests.csproj`
- Create: `Retailo.Tests/Support/TestAppDbContext.cs`
- Create: `Retailo.Tests/HarnessTests.cs`
- Modify: `Retailo.sln` (add test project)

**Interfaces:**
- Produces: `Retailo.Tests.Support.TestAppDbContext(string dbName, int tenantId)`, an `AppDBContext` subclass backed by EF InMemory. All later tests construct it. Two contexts with the same `dbName` and different `tenantId` share data but see only their own tenant (this proves the tenant filter).

- [ ] **Step 1: Create the branch**

The branch already exists (created 2026-10-04 from `main`). Verify and stay on it:

```bash
cd /d/git/Retailo_v1
git branch --show-current          # expect: Retail_MissionCommerceAI
git status --short | head -5       # ~87 unrelated modified files travelled with the checkout; leave them alone
```

- [ ] **Step 2: Create the test project file**

`Retailo.Tests/Retailo.Tests.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>disable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.11.1" />
    <PackageReference Include="xunit" Version="2.9.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="7.0.13" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\Retailo.csproj" />
  </ItemGroup>

</Project>
```

- [ ] **Step 3: Create the test DbContext**

`Retailo.Tests/Support/TestAppDbContext.cs`:

```csharp
using GoPosify.Data;
using Microsoft.EntityFrameworkCore;

namespace Retailo.Tests.Support;

// AppDBContext.OnConfiguring hard-wires SQL Server, so tests subclass it and swap in InMemory.
public sealed class TestAppDbContext : AppDBContext
{
    private readonly string _dbName;

    public TestAppDbContext(string dbName, int tenantId)
    {
        _dbName = dbName;
        CurrentTenantId = tenantId;
    }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        => optionsBuilder.UseInMemoryDatabase(_dbName);

    public static string NewDbName() => Guid.NewGuid().ToString("N");
}
```

- [ ] **Step 4: Write the harness test**

`Retailo.Tests/HarnessTests.cs`:

```csharp
using GoPosify.Models;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class HarnessTests
{
    [Fact]
    public async Task Tenant_filter_isolates_rows_between_contexts_sharing_one_database()
    {
        var name = TestAppDbContext.NewDbName();

        await using (var tenant7 = new TestAppDbContext(name, 7))
        {
            tenant7.Warehouses.Add(new Warehouse { WarehouseName = "Branch A" });
            await tenant7.SaveChangesAsync();
        }

        await using var seen7 = new TestAppDbContext(name, 7);
        await using var seen8 = new TestAppDbContext(name, 8);

        Assert.Equal(1, seen7.Warehouses.Count(w => w.WarehouseName == "Branch A"));
        Assert.Equal(0, seen8.Warehouses.Count(w => w.WarehouseName == "Branch A"));
    }
}
```

- [ ] **Step 5: Add to solution and run**

```bash
cd /d/git/Retailo_v1
dotnet sln Retailo.sln add Retailo.Tests/Retailo.Tests.csproj
dotnet test Retailo.Tests/Retailo.Tests.csproj
```

Expected: build succeeds and `Passed: 1`. **If the build fails or the test fails**, the cause is the harness (most likely InMemory rejecting some SQL-Server-specific model configuration, or a missing package restore). Fix the harness before continuing. Do not proceed to later tasks with a broken harness. If InMemory cannot load the model at all, report to the user: the fallback is a SQL Server LocalDB test database, which changes every later test's setup.

- [ ] **Step 6: Commit**

```bash
git add Retailo.Tests/Retailo.Tests.csproj Retailo.Tests/Support/TestAppDbContext.cs Retailo.Tests/HarnessTests.cs Retailo.sln
git commit -m "test: add xUnit harness with InMemory AppDBContext"
```

---

### Task 3: Onboarding contract smoke (Register to AddWarehouse, routes)

**Files (hackathon repo):**
- Create: `pesoweb-additions/smoke/common.ps1`
- Create: `pesoweb-additions/smoke/onboarding-contract.ps1`
- Create: `Docs/onboarding-contract.md`

**Interfaces:**
- Produces in `common.ps1`:
  - `New-SimTenant -BaseUrl <string> -Prefix <string>` returns an object `{ Token, TenantID, WarehouseId, Email, Password }` (registers a fresh tenant, which also logs in).
  - `Invoke-PesoApi -BaseUrl <string> -Token <string> -Method <string> -Path <string> [-Body <object>] [-SimRun <string>]` returns the parsed JSON response and throws on HTTP error with the response body in the message.
- Learned facts (recorded in `Docs/onboarding-contract.md`): the working `Register` -> `Login` shape, the default warehouse the registration creates, the exact routes for users, categories/brands/units/tax rates and products. Plan 3's `PesoWebDriver` depends on this document.

- [ ] **Step 1: Start PesoWeb locally**

```powershell
cd D:\git\Retailo_v1
dotnet run --project Retailo.csproj --urls http://localhost:5061
```

Expected: the app listens on `http://localhost:5061`. If the SPA proxy tries to launch `npm start`, it can be ignored; only the API is used. Leave it running.

- [ ] **Step 2: Write the helpers**

`pesoweb-additions/smoke/common.ps1`:

```powershell
function Invoke-PesoApi {
    param(
        [Parameter(Mandatory)] [string] $BaseUrl,
        [string] $Token,
        [Parameter(Mandatory)] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        $Body,
        [string] $SimRun
    )
    $headers = @{}
    if ($Token)  { $headers['Authorization'] = "Bearer $Token" }
    if ($SimRun) { $headers['X-Sim-Run'] = $SimRun }
    $args = @{ Uri = "$BaseUrl$Path"; Method = $Method; Headers = $headers; ContentType = 'application/json' }
    if ($null -ne $Body) { $args['Body'] = ($Body | ConvertTo-Json -Depth 8) }
    try {
        return Invoke-RestMethod @args
    } catch {
        $detail = ''
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail = $reader.ReadToEnd()
        }
        throw "API $Method $Path failed: $($_.Exception.Message) $detail"
    }
}

function New-SimTenant {
    param(
        [Parameter(Mandatory)] [string] $BaseUrl,
        [string] $Prefix = 'sim'
    )
    $id = [guid]::NewGuid().ToString('N').Substring(0, 10)
    $email = "$Prefix+$id@example.test"
    $password = "Sim!$id"
    $body = @{
        CompanyName = "$Prefix store $id"; FirstName = 'Sim'; LastName = 'Owner'
        Email = $email; Phone = '+639000000000'; Password = $password; ConfirmPassword = $password
    }
    $r = Invoke-PesoApi -BaseUrl $BaseUrl -Method POST -Path '/api/Auth/Register' -Body $body
    return [pscustomobject]@{
        Token = $r.token; TenantID = $r.tenantID; WarehouseId = $r.defaultWarehouseId
        Email = $email; Password = $password; Permissions = $r.permissions
    }
}
```

- [ ] **Step 3: Write the contract script**

`pesoweb-additions/smoke/onboarding-contract.ps1`:

```powershell
param([string] $BaseUrl = 'http://localhost:5061')
. "$PSScriptRoot\common.ps1"

$t = New-SimTenant -BaseUrl $BaseUrl -Prefix 'contract'
Write-Host "Registered tenant $($t.TenantID), default warehouse $($t.WarehouseId)"
if (-not $t.Token)       { throw 'Register did not return a token' }
if (-not $t.WarehouseId) { throw 'Register did not return a default warehouse id' }

# Second branch through the real endpoint (bounded by the tier limit; a fresh tenant should be on the entry tier)
try {
    $wh = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/Settings/AddWarehouse' -Body @{
        WarehouseName = 'Contract Branch 2'; Email = 'b2@example.test'; Phone = '+639000000001'
        Address = '1 Test St'; City = 'Manila'; State = 'NCR'; PostalCode = '1000'; Country = 'PH'
    }
    Write-Host "AddWarehouse OK: id $($wh.id)"
} catch {
    Write-Host "AddWarehouse refused (expected on a 1-branch tier): $_"
}

# Discover the routes the driver will need
$swagger = Invoke-RestMethod -Uri "$BaseUrl/swagger/v1/swagger.json" -Method GET
$swagger.paths.PSObject.Properties.Name |
    Where-Object { $_ -match '/(AddUser|AddProduct|Categories|Brands|Units|TaxRates|PaymentMethods|AddPurchase|AddSale)' } |
    Sort-Object | ForEach-Object { Write-Host "ROUTE $_" }
```

- [ ] **Step 4: Run it**

Run: `powershell -File pesoweb-additions/smoke/onboarding-contract.ps1`
Expected: "Registered tenant N, default warehouse M", then either an AddWarehouse success or the tier-limit refusal text, then a list of `ROUTE /api/...` lines. If Register fails, the error text includes the server response; fix the payload using `DTO/RegisterDTO.cs` in PesoWeb (required: CompanyName, Email, Password, ConfirmPassword).

- [ ] **Step 5: Verify the rest of the chain by hand and document it**

Using the `ROUTE` list, make real calls with `Invoke-PesoApi` (or Swagger UI at `http://localhost:5061/swagger`) to confirm each link of the chain: create a second staff user (`UserDTO` requires RoleId, FullName, UserName, Email, Password, IsActive, IsTwoFactorEnabled; it is a multipart form), list categories/brands/units/tax rates that the new tenant already has, and create one product (`ProductDTO` requires CategoryId, BrandId, UnitId, SaleUnitId, PurchaseUnitId, TaxId, TaxMethod, ProductCode, BarcodeType, ProductName, Cost, Price, Discount; multipart form). Write `Docs/onboarding-contract.md` with, for each step: route, HTTP method, content type, minimal working payload, and the observed response. Mark any link that fails with the exact error. A failing link is a finding for Plan 3, not a reason to change PesoWeb now.

- [ ] **Step 6: Commit**

```bash
git add pesoweb-additions/smoke/common.ps1 pesoweb-additions/smoke/onboarding-contract.ps1 Docs/onboarding-contract.md
git commit -m "P0: verify signup-to-catalog chain and record onboarding contract"
```

---

### Task 4: Business event outbox

**Files (PesoWeb):**
- Create: `Models/BusinessEvent.cs`
- Create: `Services/BusinessEventPublisher.cs`
- Modify: `Data/AppDBContext.cs` (add DbSet), `Program.cs` (DI)
- Test: `Retailo.Tests/BusinessEventPublisherTests.cs`
- Generated: migration `AddBusinessEvents`

**Interfaces:**
- Produces:
  - `GoPosify.Models.BusinessEvent` with `long Id, int TenantID, int? WarehouseId, string EventType, string ReferenceNo, string PayloadJson, string SimRunId, DateTime OccurredAt`
  - `GoPosify.Services.BusinessEventTypes` constants: `SaleCompleted`, `CashOpened`, `CashClosed`
  - `GoPosify.Services.IBusinessEventPublisher.Publish(string eventType, int? warehouseId, string referenceNo, object payload, DateTime occurredAt)`. It **adds** to the context and does **not** call SaveChanges; the caller saves in its own unit of work.
  - `BusinessEventPublisher.SimRunHeader` = `"X-Sim-Run"`
  - `AppDBContext.BusinessEvents`

- [ ] **Step 1: Write the failing tests**

`Retailo.Tests/BusinessEventPublisherTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Microsoft.AspNetCore.Http;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class BusinessEventPublisherTests
{
    private static IHttpContextAccessor AccessorWithHeader(string value)
    {
        var ctx = new DefaultHttpContext();
        if (value != null) ctx.Request.Headers[BusinessEventPublisher.SimRunHeader] = value;
        return new HttpContextAccessor { HttpContext = ctx };
    }

    [Fact]
    public async Task Publish_adds_event_with_tenant_payload_and_time_and_no_sim_run()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        var publisher = new BusinessEventPublisher(db, AccessorWithHeader(null));
        var at = new DateTime(2026, 10, 20, 9, 30, 0);

        publisher.Publish(BusinessEventTypes.CashOpened, 3, "shift-1", new { shiftId = 1, openingCash = 1000m }, at);
        await db.SaveChangesAsync();

        var e = Assert.Single(db.BusinessEvents.ToList());
        Assert.Equal(5, e.TenantID);
        Assert.Equal(3, e.WarehouseId);
        Assert.Equal("CashOpened", e.EventType);
        Assert.Equal("shift-1", e.ReferenceNo);
        Assert.Equal(at, e.OccurredAt);
        Assert.Contains("\"openingCash\":1000", e.PayloadJson);
        Assert.Null(e.SimRunId);
    }

    [Fact]
    public async Task Publish_tags_sim_run_from_header()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        var publisher = new BusinessEventPublisher(db, AccessorWithHeader("run-42"));

        publisher.Publish(BusinessEventTypes.SaleCompleted, 3, "s-9", new { saleId = 9 }, DateTime.UtcNow);
        await db.SaveChangesAsync();

        Assert.Equal("run-42", db.BusinessEvents.Single().SimRunId);
    }

    [Fact]
    public async Task Publish_truncates_sim_run_to_64_chars()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        var publisher = new BusinessEventPublisher(db, AccessorWithHeader(new string('x', 100)));

        publisher.Publish(BusinessEventTypes.SaleCompleted, null, "s-1", new { }, DateTime.UtcNow);
        await db.SaveChangesAsync();

        Assert.Equal(64, db.BusinessEvents.Single().SimRunId.Length);
    }

    [Fact]
    public async Task Publish_does_not_save_until_caller_saves()
    {
        var name = TestAppDbContext.NewDbName();
        await using var db = new TestAppDbContext(name, 5);
        var publisher = new BusinessEventPublisher(db, AccessorWithHeader(null));

        publisher.Publish(BusinessEventTypes.CashClosed, 1, "shift-2", new { }, DateTime.UtcNow);

        await using var other = new TestAppDbContext(name, 5);
        Assert.Empty(other.BusinessEvents.ToList());
    }
}
```

- [ ] **Step 2: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter BusinessEventPublisherTests`
Expected: build FAIL (`BusinessEvent`, `BusinessEventPublisher` not defined).

- [ ] **Step 3: Add the model**

`Models/BusinessEvent.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace GoPosify.Models;

[Index(nameof(TenantID), nameof(Id), Name = "IX_BusinessEvents_Tenant_Id")]
public partial class BusinessEvent
{
    [Key]
    public long Id { get; set; }

    public int TenantID { get; set; }

    public int? WarehouseId { get; set; }

    [Required]
    [StringLength(60)]
    public string EventType { get; set; }

    [StringLength(100)]
    public string ReferenceNo { get; set; }

    public string PayloadJson { get; set; }

    [StringLength(64)]
    public string SimRunId { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime OccurredAt { get; set; }
}
```

- [ ] **Step 4: Add the DbSet**

In `Data/AppDBContext.cs`, next to the other `DbSet` declarations (for example after `public virtual DbSet<AuditLog> AuditLogs { get; set; }`) add:

```csharp
    public virtual DbSet<BusinessEvent> BusinessEvents { get; set; }
```

- [ ] **Step 5: Add the publisher**

`Services/BusinessEventPublisher.cs`:

```csharp
using System.Text.Json;
using GoPosify.Data;
using GoPosify.Models;
using Microsoft.AspNetCore.Http;

namespace GoPosify.Services;

public static class BusinessEventTypes
{
    public const string SaleCompleted = "SaleCompleted";
    public const string CashOpened = "CashOpened";
    public const string CashClosed = "CashClosed";
}

public interface IBusinessEventPublisher
{
    // Adds to the current DbContext; the caller owns SaveChanges so the event commits with its business change.
    void Publish(string eventType, int? warehouseId, string referenceNo, object payload, DateTime occurredAt);
}

public sealed class BusinessEventPublisher : IBusinessEventPublisher
{
    public const string SimRunHeader = "X-Sim-Run";

    private readonly AppDBContext _db;
    private readonly IHttpContextAccessor _http;

    public BusinessEventPublisher(AppDBContext db, IHttpContextAccessor http)
    {
        _db = db;
        _http = http;
    }

    public void Publish(string eventType, int? warehouseId, string referenceNo, object payload, DateTime occurredAt)
    {
        var simRun = _http?.HttpContext?.Request?.Headers[SimRunHeader].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(simRun))
        {
            simRun = null;
        }
        else if (simRun.Length > 64)
        {
            simRun = simRun.Substring(0, 64);
        }

        _db.BusinessEvents.Add(new BusinessEvent
        {
            TenantID = _db.CurrentTenantId > 0 ? _db.CurrentTenantId : 1,
            WarehouseId = warehouseId,
            EventType = eventType,
            ReferenceNo = referenceNo,
            PayloadJson = JsonSerializer.Serialize(payload),
            SimRunId = simRun,
            OccurredAt = occurredAt
        });
    }
}
```

- [ ] **Step 6: Register in DI**

In `Program.cs`, after the line `builder.Services.AddScoped<IInventoryBatchService, InventoryBatchService>();` add:

```csharp
builder.Services.AddScoped<IBusinessEventPublisher, BusinessEventPublisher>();
```

- [ ] **Step 7: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter BusinessEventPublisherTests`
Expected: `Passed: 4`.

- [ ] **Step 8: Generate and inspect the migration**

```bash
cd /d/git/Retailo_v1
dotnet ef migrations add AddBusinessEvents --project Retailo.csproj
```

Open the generated `Migrations/*_AddBusinessEvents.cs`. **It must contain only** `CreateTable("BusinessEvents", ...)` plus its index and the matching `DropTable` in `Down`. If it contains anything else (other tables, `AlterColumn`, seed `UpdateData`), the model snapshot was already out of sync with the code: delete the generated migration files (`git clean` only those new files and restore `Migrations/AppDBContextModelSnapshot.cs` with `git checkout -- Migrations/AppDBContextModelSnapshot.cs`), stop, and report to the user. Do not ship unrelated schema changes.

- [ ] **Step 9: Apply to the local dev database and build**

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
```

Expected: migration applies; build succeeds with no errors.

- [ ] **Step 10: Commit**

```bash
git add Models/BusinessEvent.cs Services/BusinessEventPublisher.cs Data/AppDBContext.cs Program.cs Retailo.Tests/BusinessEventPublisherTests.cs Migrations/*AddBusinessEvents*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: business event outbox with X-Sim-Run tagging"
```

---

### Task 5: Cash shift entities, Sale columns, audit context columns

**Files (PesoWeb):**
- Create: `Models/CashShift.cs`
- Modify: `Models/Sale.cs`, `Models/AuditLog.cs`, `Data/AppDBContext.cs`
- Generated: migration `AddCashShiftsAndAuditContext`

**Interfaces:**
- Produces:
  - `CashShift { int Id, int TenantID, int WarehouseId, int CashierId, string PosTerminal, DateTime OpenedAt, decimal OpeningCash, DateTime? ClosedAt, decimal? ExpectedCash, decimal? ActualCash, decimal? Variance, string Status, string Note, DateTime? UpdatedAt }`
  - `CashMovement { long Id, int TenantID, int ShiftId, string MovementType, decimal Amount, string Reason, string ReferenceNo, int CreatedBy, DateTime CreatedAt }`
  - `Sale.ShiftId int?`, `Sale.CashierId int?`, `Sale.PosTerminal string`
  - `AuditLog.WarehouseId int?`, `AuditLog.ReferenceNo string`, `AuditLog.BeforeValue string`, `AuditLog.AfterValue string`
  - `AppDBContext.CashShifts`, `AppDBContext.CashMovements`

- [ ] **Step 1: Add the models**

`Models/CashShift.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace GoPosify.Models;

[Index(nameof(TenantID), nameof(CashierId), nameof(Status), Name = "IX_CashShifts_Tenant_Cashier_Status")]
public partial class CashShift
{
    [Key]
    public int Id { get; set; }

    public int TenantID { get; set; }

    public int WarehouseId { get; set; }

    public int CashierId { get; set; }

    [StringLength(50)]
    public string PosTerminal { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime OpenedAt { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal OpeningCash { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? ClosedAt { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal? ExpectedCash { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal? ActualCash { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal? Variance { get; set; }

    [Required]
    [StringLength(20)]
    public string Status { get; set; }

    [StringLength(500)]
    public string Note { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime? UpdatedAt { get; set; }
}

[Index(nameof(TenantID), nameof(ShiftId), Name = "IX_CashMovements_Tenant_Shift")]
public partial class CashMovement
{
    [Key]
    public long Id { get; set; }

    public int TenantID { get; set; }

    public int ShiftId { get; set; }

    [Required]
    [StringLength(20)]
    public string MovementType { get; set; }

    [Column(TypeName = "decimal(18, 2)")]
    public decimal Amount { get; set; }

    [StringLength(300)]
    public string Reason { get; set; }

    [StringLength(100)]
    public string ReferenceNo { get; set; }

    public int CreatedBy { get; set; }

    [Column(TypeName = "datetime")]
    public DateTime CreatedAt { get; set; }
}
```

- [ ] **Step 2: Add nullable columns to Sale**

In `Models/Sale.cs`, after the `UpdatedBy` property (`public string UpdatedBy { get; set; }`) add:

```csharp
    public int? ShiftId { get; set; }

    public int? CashierId { get; set; }

    [StringLength(50)]
    public string PosTerminal { get; set; }
```

- [ ] **Step 3: Extend AuditLog**

In `Models/AuditLog.cs`, after `public DateTime Timestamp { get; set; }` add:

```csharp
    public int? WarehouseId { get; set; }

    [StringLength(100)]
    public string ReferenceNo { get; set; }

    public string BeforeValue { get; set; }

    public string AfterValue { get; set; }
```

- [ ] **Step 4: Add DbSets**

In `Data/AppDBContext.cs`, next to `BusinessEvents`:

```csharp
    public virtual DbSet<CashShift> CashShifts { get; set; }

    public virtual DbSet<CashMovement> CashMovements { get; set; }
```

- [ ] **Step 5: Build and run all tests (nothing should break)**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all existing tests pass.

- [ ] **Step 6: Generate and inspect the migration**

```bash
dotnet ef migrations add AddCashShiftsAndAuditContext --project Retailo.csproj
```

The migration must contain **only**: `CreateTable CashShifts`, `CreateTable CashMovements` (with indexes), `AddColumn` for `Sales.ShiftId/CashierId/PosTerminal` (all nullable), and `AddColumn` for `AuditLogs.WarehouseId/ReferenceNo/BeforeValue/AfterValue` (all nullable). Anything else: apply the same stop-and-report rule as Task 4 Step 8.

- [ ] **Step 7: Apply, build, commit**

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
git add Models/CashShift.cs Models/Sale.cs Models/AuditLog.cs Data/AppDBContext.cs Migrations/*AddCashShiftsAndAuditContext*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: cash shift tables, nullable sale shift columns, audit context columns"
```

---

### Task 6: Cash shift service (expected cash and variance)

**Files (PesoWeb):**
- Create: `Services/CashShiftService.cs`
- Modify: `Program.cs` (DI)
- Test: `Retailo.Tests/CashShiftServiceTests.cs`

**Interfaces:**
- Consumes: `IBusinessEventPublisher`, `BusinessEventTypes`, `CashShift`, `CashMovement`, `Sale.ShiftId`.
- Produces in `GoPosify.Services`:
  - `CashShiftStatus.Open = "Open"`, `CashShiftStatus.Closed = "Closed"`
  - `CashMovementType.CashIn = "CashIn"`, `CashOut = "CashOut"`, `Refund = "Refund"`; `CashMovementType.All` (string[])
  - `CashShiftCalculator.ExpectedCash(decimal openingCash, decimal cashSales, decimal cashIn, decimal cashRefunds, decimal cashOut)` and `CashShiftCalculator.Variance(decimal actualCash, decimal expectedCash)`
  - `CashShiftSummary { decimal OpeningCash, CashSales, CashIn, CashRefunds, CashOut, ExpectedCash }`
  - `ICashShiftService`:
    - `Task<CashShift> OpenAsync(int warehouseId, int cashierId, string posTerminal, decimal openingCash, DateTime now)`
    - `Task<CashMovement> AddMovementAsync(int shiftId, string movementType, decimal amount, string reason, string referenceNo, int userId, DateTime now)`
    - `Task<CashShiftSummary> SummarizeAsync(int shiftId)`
    - `Task<CashShift> CloseAsync(int shiftId, decimal actualCash, string note, DateTime now)`
  - All invalid operations throw `InvalidOperationException` with a user-safe message.
- Scope note: cash refunds come only from `CashMovement` rows of type `Refund`. Plan 2 (sale lifecycle) makes sale returns create these rows automatically.

- [ ] **Step 1: Write the failing tests**

`Retailo.Tests/CashShiftServiceTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Microsoft.AspNetCore.Http;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class CashShiftServiceTests
{
    private static readonly DateTime T0 = new(2026, 10, 20, 8, 0, 0);

    private static (TestAppDbContext db, CashShiftService svc) Create(int tenantId = 5)
    {
        var db = new TestAppDbContext(TestAppDbContext.NewDbName(), tenantId);
        var publisher = new BusinessEventPublisher(db, new HttpContextAccessor { HttpContext = new DefaultHttpContext() });
        return (db, new CashShiftService(db, publisher));
    }

    private static Sale CashSale(int shiftId, decimal total, decimal paid, string method = "Cash")
        => new()
        {
            WarehouseId = 1, CustomerId = 1, SaleDate = T0, PaymentMethod = method, ShiftId = shiftId,
            TotalAmount = total, PaidAmount = paid, ChangeDue = paid > total ? paid - total : 0
        };

    [Fact]
    public void Calculator_matches_the_deck_example()
    {
        var expected = CashShiftCalculator.ExpectedCash(10000m, 35000m, 0m, 2000m, 0m);
        Assert.Equal(43000m, expected);
        Assert.Equal(-1500m, CashShiftCalculator.Variance(41500m, expected));
    }

    [Fact]
    public async Task Open_creates_open_shift_and_publishes_CashOpened()
    {
        var (db, svc) = Create();
        await using var _ = db;

        var shift = await svc.OpenAsync(1, 77, "POS-01", 10000m, T0);

        Assert.Equal(CashShiftStatus.Open, shift.Status);
        Assert.Equal(10000m, shift.OpeningCash);
        Assert.Equal(5, shift.TenantID);
        var ev = Assert.Single(db.BusinessEvents.ToList());
        Assert.Equal(BusinessEventTypes.CashOpened, ev.EventType);
        Assert.Equal($"shift-{shift.Id}", ev.ReferenceNo);
    }

    [Fact]
    public async Task Open_rejects_second_open_shift_for_the_same_cashier()
    {
        var (db, svc) = Create();
        await using var _ = db;
        await svc.OpenAsync(1, 77, "POS-01", 100m, T0);

        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() => svc.OpenAsync(2, 77, "POS-02", 100m, T0));
        Assert.Contains("already has an open shift", ex.Message);
    }

    [Fact]
    public async Task Open_rejects_negative_opening_cash()
    {
        var (db, svc) = Create();
        await using var _ = db;
        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.OpenAsync(1, 77, "POS-01", -1m, T0));
    }

    [Fact]
    public async Task Close_computes_expected_cash_and_variance_from_sales_and_movements()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 10000m, T0);
        db.Sales.Add(CashSale(shift.Id, 35000m, 35000m));
        await db.SaveChangesAsync();
        await svc.AddMovementAsync(shift.Id, CashMovementType.Refund, 2000m, "customer return", "sr-1", 77, T0);

        var closed = await svc.CloseAsync(shift.Id, 41500m, null, T0.AddHours(9));

        Assert.Equal(CashShiftStatus.Closed, closed.Status);
        Assert.Equal(43000m, closed.ExpectedCash);
        Assert.Equal(41500m, closed.ActualCash);
        Assert.Equal(-1500m, closed.Variance);
        Assert.Contains(db.BusinessEvents.ToList(), e => e.EventType == BusinessEventTypes.CashClosed);
    }

    [Fact]
    public async Task Cash_sale_counts_net_of_change_given()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 0m, T0);
        db.Sales.Add(CashSale(shift.Id, total: 450m, paid: 500m));   // 50 given back as change
        await db.SaveChangesAsync();

        var summary = await svc.SummarizeAsync(shift.Id);

        Assert.Equal(450m, summary.CashSales);
    }

    [Fact]
    public async Task Non_cash_sales_are_excluded_from_cash_sales()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 0m, T0);
        db.Sales.Add(CashSale(shift.Id, 300m, 300m, method: "GCash"));
        db.Sales.Add(CashSale(shift.Id, 100m, 100m, method: "cash"));
        await db.SaveChangesAsync();

        var summary = await svc.SummarizeAsync(shift.Id);

        Assert.Equal(100m, summary.CashSales);
    }

    [Fact]
    public async Task Cash_in_and_cash_out_move_expected_cash()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 1000m, T0);
        await svc.AddMovementAsync(shift.Id, CashMovementType.CashIn, 200m, "float top-up", null, 77, T0);
        await svc.AddMovementAsync(shift.Id, CashMovementType.CashOut, 500m, "supplier cash", null, 77, T0);

        var summary = await svc.SummarizeAsync(shift.Id);

        Assert.Equal(700m, summary.ExpectedCash);
    }

    [Theory]
    [InlineData("Bogus", 10)]
    [InlineData(CashMovementType.CashIn, 0)]
    [InlineData(CashMovementType.CashOut, -5)]
    public async Task Movement_rejects_unknown_type_and_non_positive_amount(string type, int amount)
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 100m, T0);

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => svc.AddMovementAsync(shift.Id, type, amount, "x", null, 77, T0));
    }

    [Fact]
    public async Task Movement_and_close_are_rejected_on_a_closed_shift()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 100m, T0);
        await svc.CloseAsync(shift.Id, 100m, null, T0.AddHours(8));

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => svc.AddMovementAsync(shift.Id, CashMovementType.CashIn, 10m, "late", null, 77, T0));
        await Assert.ThrowsAsync<InvalidOperationException>(
            () => svc.CloseAsync(shift.Id, 100m, null, T0.AddHours(9)));
    }

    [Fact]
    public async Task Close_rejects_negative_actual_cash_and_unknown_shift()
    {
        var (db, svc) = Create();
        await using var _ = db;
        var shift = await svc.OpenAsync(1, 77, "POS-01", 100m, T0);

        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.CloseAsync(shift.Id, -1m, null, T0));
        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.CloseAsync(99999, 0m, null, T0));
    }
}
```

- [ ] **Step 2: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter CashShiftServiceTests`
Expected: build FAIL (`CashShiftService`, `CashShiftCalculator`, etc. not defined).

- [ ] **Step 3: Implement**

`Services/CashShiftService.cs`:

```csharp
using GoPosify.Data;
using GoPosify.Models;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Services;

public static class CashShiftStatus
{
    public const string Open = "Open";
    public const string Closed = "Closed";
}

public static class CashMovementType
{
    public const string CashIn = "CashIn";
    public const string CashOut = "CashOut";
    public const string Refund = "Refund";

    public static readonly string[] All = { CashIn, CashOut, Refund };
}

public static class CashShiftCalculator
{
    // Expected = Opening + CashSales + CashIn - CashRefunds - CashOut
    public static decimal ExpectedCash(decimal openingCash, decimal cashSales, decimal cashIn, decimal cashRefunds, decimal cashOut)
        => openingCash + cashSales + cashIn - cashRefunds - cashOut;

    // Variance = Actual - Expected (negative means the drawer is short)
    public static decimal Variance(decimal actualCash, decimal expectedCash) => actualCash - expectedCash;
}

public sealed class CashShiftSummary
{
    public decimal OpeningCash { get; set; }
    public decimal CashSales { get; set; }
    public decimal CashIn { get; set; }
    public decimal CashRefunds { get; set; }
    public decimal CashOut { get; set; }
    public decimal ExpectedCash { get; set; }
}

public interface ICashShiftService
{
    Task<CashShift> OpenAsync(int warehouseId, int cashierId, string posTerminal, decimal openingCash, DateTime now);
    Task<CashMovement> AddMovementAsync(int shiftId, string movementType, decimal amount, string reason, string referenceNo, int userId, DateTime now);
    Task<CashShiftSummary> SummarizeAsync(int shiftId);
    Task<CashShift> CloseAsync(int shiftId, decimal actualCash, string note, DateTime now);
}

public sealed class CashShiftService : ICashShiftService
{
    private readonly AppDBContext _db;
    private readonly IBusinessEventPublisher _events;

    public CashShiftService(AppDBContext db, IBusinessEventPublisher events)
    {
        _db = db;
        _events = events;
    }

    public async Task<CashShift> OpenAsync(int warehouseId, int cashierId, string posTerminal, decimal openingCash, DateTime now)
    {
        if (openingCash < 0)
        {
            throw new InvalidOperationException("Opening cash cannot be negative.");
        }

        var alreadyOpen = await _db.CashShifts.AnyAsync(s => s.CashierId == cashierId && s.Status == CashShiftStatus.Open);
        if (alreadyOpen)
        {
            throw new InvalidOperationException("This cashier already has an open shift. Close it first.");
        }

        var shift = new CashShift
        {
            WarehouseId = warehouseId,
            CashierId = cashierId,
            PosTerminal = posTerminal,
            OpenedAt = now,
            OpeningCash = openingCash,
            Status = CashShiftStatus.Open
        };
        _db.CashShifts.Add(shift);
        await _db.SaveChangesAsync();   // assigns Id for the event reference

        _events.Publish(BusinessEventTypes.CashOpened, warehouseId, $"shift-{shift.Id}",
            new { shiftId = shift.Id, cashierId, posTerminal, openingCash }, now);
        await _db.SaveChangesAsync();
        return shift;
    }

    public async Task<CashMovement> AddMovementAsync(int shiftId, string movementType, decimal amount, string reason, string referenceNo, int userId, DateTime now)
    {
        if (!CashMovementType.All.Contains(movementType))
        {
            throw new InvalidOperationException($"Unknown cash movement type '{movementType}'.");
        }

        if (amount <= 0)
        {
            throw new InvalidOperationException("Amount must be greater than zero.");
        }

        var shift = await GetOpenShiftAsync(shiftId);
        var movement = new CashMovement
        {
            ShiftId = shift.Id,
            MovementType = movementType,
            Amount = amount,
            Reason = reason,
            ReferenceNo = referenceNo,
            CreatedBy = userId,
            CreatedAt = now
        };
        _db.CashMovements.Add(movement);
        await _db.SaveChangesAsync();
        return movement;
    }

    public async Task<CashShiftSummary> SummarizeAsync(int shiftId)
    {
        var shift = await _db.CashShifts.AsNoTracking().FirstOrDefaultAsync(s => s.Id == shiftId)
            ?? throw new InvalidOperationException("Shift not found.");

        var sales = await _db.Sales.AsNoTracking()
            .Where(s => s.ShiftId == shiftId)
            .Select(s => new { s.PaymentMethod, s.PaidAmount, s.ChangeDue })
            .ToListAsync();
        var cashSales = sales
            .Where(s => string.Equals(s.PaymentMethod, "Cash", StringComparison.OrdinalIgnoreCase))
            .Sum(s => s.PaidAmount - s.ChangeDue);

        var movements = await _db.CashMovements.AsNoTracking().Where(m => m.ShiftId == shiftId).ToListAsync();
        decimal Sum(string type) => movements.Where(m => m.MovementType == type).Sum(m => m.Amount);

        var cashIn = Sum(CashMovementType.CashIn);
        var cashOut = Sum(CashMovementType.CashOut);
        var refunds = Sum(CashMovementType.Refund);

        return new CashShiftSummary
        {
            OpeningCash = shift.OpeningCash,
            CashSales = cashSales,
            CashIn = cashIn,
            CashOut = cashOut,
            CashRefunds = refunds,
            ExpectedCash = CashShiftCalculator.ExpectedCash(shift.OpeningCash, cashSales, cashIn, refunds, cashOut)
        };
    }

    public async Task<CashShift> CloseAsync(int shiftId, decimal actualCash, string note, DateTime now)
    {
        if (actualCash < 0)
        {
            throw new InvalidOperationException("Counted cash cannot be negative.");
        }

        var shift = await GetOpenShiftAsync(shiftId);
        var summary = await SummarizeAsync(shiftId);

        shift.ExpectedCash = summary.ExpectedCash;
        shift.ActualCash = actualCash;
        shift.Variance = CashShiftCalculator.Variance(actualCash, summary.ExpectedCash);
        shift.ClosedAt = now;
        shift.Note = note;
        shift.Status = CashShiftStatus.Closed;

        _events.Publish(BusinessEventTypes.CashClosed, shift.WarehouseId, $"shift-{shift.Id}",
            new { shiftId = shift.Id, shift.CashierId, shift.OpeningCash, expectedCash = shift.ExpectedCash, actualCash, variance = shift.Variance }, now);
        await _db.SaveChangesAsync();
        return shift;
    }

    private async Task<CashShift> GetOpenShiftAsync(int shiftId)
    {
        var shift = await _db.CashShifts.FirstOrDefaultAsync(s => s.Id == shiftId)
            ?? throw new InvalidOperationException("Shift not found.");
        if (shift.Status != CashShiftStatus.Open)
        {
            throw new InvalidOperationException("This shift is already closed.");
        }

        return shift;
    }
}
```

- [ ] **Step 4: Register in DI**

In `Program.cs`, after the `IBusinessEventPublisher` registration:

```csharp
builder.Services.AddScoped<ICashShiftService, CashShiftService>();
```

- [ ] **Step 5: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter CashShiftServiceTests`
Expected: all pass (calculator, open x3, close variance, net-of-change, non-cash excluded, cash-in/out, movement validation x3, closed-shift rejections, close validation).

- [ ] **Step 6: Commit**

```bash
git add Services/CashShiftService.cs Program.cs Retailo.Tests/CashShiftServiceTests.cs
git commit -m "feat: cash shift service with expected cash and variance"
```

---

### Task 7: Cash shift API, permissions, and AddSale hooks

**Files (PesoWeb):**
- Create: `DTO/CashShifts/CashShiftDTOs.cs`
- Create: `Controllers/CashShiftsController.cs`
- Modify: `Helpers/Permissions.cs`, `Controllers/SalesController.cs`
- Generated: migration `GrantCashPermissionsToDefaultRole`

**Interfaces:**
- Consumes: `ICashShiftService`, `IBusinessEventPublisher`, `CashShiftStatus`, `AuditLog` extended columns.
- Produces HTTP endpoints (JSON bodies):
  - `POST api/CashShifts/Open` body `{ warehouseId, posTerminal, openingCash }` -> `CashShift`
  - `POST api/CashShifts/AddMovement` body `{ shiftId, movementType, amount, reason, referenceNo }` -> `CashMovement`
  - `GET  api/CashShifts/Current?warehouseId=` -> `{ shift, summary }` or 404 when none is open
  - `POST api/CashShifts/Close` body `{ shiftId, actualCash, note }` -> `CashShift` (with `variance`)
  - `GET  api/CashShifts/List?warehouseId=&status=` -> up to 200 shifts, newest first
  - Permissions: `Cash.Shift` (operate), `Cash.ShiftList` (list)
  - `AddSale` attaches the cashier's open shift to the sale and publishes `SaleCompleted`.

- [ ] **Step 1: Add the permissions**

In `Helpers/Permissions.cs`, in the permission list just before the `// Other` comment group, add:

```csharp
                // Cash
                "Cash.Shift", "Cash.ShiftList",
                // AI / Sim read API
                "AI.Read",
```

- [ ] **Step 2: Add DTOs**

`DTO/CashShifts/CashShiftDTOs.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace GoPosify.DTO.CashShifts;

public class OpenShiftDTO
{
    [Required] public int WarehouseId { get; set; }
    [StringLength(50)] public string PosTerminal { get; set; }
    [Range(0, 100000000)] public decimal OpeningCash { get; set; }
}

public class CashMovementDTO
{
    [Required] public int ShiftId { get; set; }
    [Required] public string MovementType { get; set; }
    public decimal Amount { get; set; }
    [StringLength(300)] public string Reason { get; set; }
    [StringLength(100)] public string ReferenceNo { get; set; }
}

public class CloseShiftDTO
{
    [Required] public int ShiftId { get; set; }
    [Range(0, 100000000)] public decimal ActualCash { get; set; }
    [StringLength(500)] public string Note { get; set; }
}
```

- [ ] **Step 3: Add the controller**

`Controllers/CashShiftsController.cs`:

```csharp
using System.Security.Claims;
using GoPosify.Data;
using GoPosify.DTO.CashShifts;
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
    public class CashShiftsController : BaseController
    {
        private readonly ICashShiftService _shifts;

        public CashShiftsController(AppDBContext dbContext, ICashShiftService shifts) : base(dbContext)
        {
            _shifts = shifts;
        }

        private int CurrentUserId() => Convert.ToInt32(User.FindFirstValue(ClaimTypes.Sid));

        private Task<bool> HasWarehouseAccessAsync(int userId, int warehouseId)
            => _dbContext.UserWarehouses.AnyAsync(uw => uw.UserId == userId && uw.WarehouseId == warehouseId);

        // POST: api/cashshifts/open
        [HttpPost]
        [Authorize(Policy = "Cash.Shift")]
        public async Task<IActionResult> Open([FromBody] OpenShiftDTO dto)
        {
            try
            {
                var userId = CurrentUserId();
                if (!await HasWarehouseAccessAsync(userId, dto.WarehouseId))
                {
                    return BadRequest(new { message = "You do not have access to this branch." });
                }

                var shift = await _shifts.OpenAsync(dto.WarehouseId, userId, dto.PosTerminal, dto.OpeningCash, CurrentDateTime());
                return Ok(shift);
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while opening the shift.", "CashShifts", "Open");
            }
        }

        // POST: api/cashshifts/addmovement
        [HttpPost]
        [Authorize(Policy = "Cash.Shift")]
        public async Task<IActionResult> AddMovement([FromBody] CashMovementDTO dto)
        {
            try
            {
                var userId = CurrentUserId();
                var shift = await _dbContext.CashShifts.AsNoTracking().FirstOrDefaultAsync(s => s.Id == dto.ShiftId);
                if (shift == null) return NotFound(new { message = "Shift not found." });
                if (shift.CashierId != userId) return BadRequest(new { message = "Only the shift's cashier can record cash movements." });

                var movement = await _shifts.AddMovementAsync(dto.ShiftId, dto.MovementType, dto.Amount, dto.Reason, dto.ReferenceNo, userId, CurrentDateTime());
                return Ok(movement);
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while recording the cash movement.", "CashShifts", "AddMovement");
            }
        }

        // GET: api/cashshifts/current?warehouseId=1
        [HttpGet]
        [Authorize(Policy = "Cash.Shift")]
        public async Task<IActionResult> Current(int warehouseId)
        {
            var userId = CurrentUserId();
            var shift = await _dbContext.CashShifts.AsNoTracking()
                .FirstOrDefaultAsync(s => s.CashierId == userId && s.WarehouseId == warehouseId && s.Status == CashShiftStatus.Open);
            if (shift == null) return NotFound(new { message = "No open shift." });

            var summary = await _shifts.SummarizeAsync(shift.Id);
            return Ok(new { shift, summary });
        }

        // POST: api/cashshifts/close
        [HttpPost]
        [Authorize(Policy = "Cash.Shift")]
        public async Task<IActionResult> Close([FromBody] CloseShiftDTO dto)
        {
            try
            {
                var userId = CurrentUserId();
                var existing = await _dbContext.CashShifts.AsNoTracking().FirstOrDefaultAsync(s => s.Id == dto.ShiftId);
                if (existing == null) return NotFound(new { message = "Shift not found." });
                if (existing.CashierId != userId) return BadRequest(new { message = "Only the shift's cashier can close it." });

                var closed = await _shifts.CloseAsync(dto.ShiftId, dto.ActualCash, dto.Note, CurrentDateTime());

                await SaveLog(new AuditLog
                {
                    Username = User.FindFirstValue(ClaimTypes.NameIdentifier) ?? "unknown",
                    Ip = HttpContext.Connection.RemoteIpAddress?.ToString() ?? "unknown",
                    Service = "CashShifts",
                    Action = "Close",
                    Status = "Success",
                    Description = $"Shift {closed.Id} closed. Unexplained variance is reported, not assumed.",
                    WarehouseId = closed.WarehouseId,
                    ReferenceNo = $"shift-{closed.Id}",
                    BeforeValue = $"Open, opening {closed.OpeningCash}",
                    AfterValue = $"expected {closed.ExpectedCash}, actual {closed.ActualCash}, variance {closed.Variance}"
                });

                return Ok(closed);
            }
            catch (InvalidOperationException ex)
            {
                return BadRequest(new { message = ex.Message });
            }
            catch (Exception ex)
            {
                return HandleServerError(ex, "An error occurred while closing the shift.", "CashShifts", "Close");
            }
        }

        // GET: api/cashshifts/list?warehouseId=1&status=Closed
        [HttpGet]
        [Authorize(Policy = "Cash.ShiftList")]
        public async Task<IActionResult> List(int? warehouseId, string status)
        {
            var q = _dbContext.CashShifts.AsNoTracking().AsQueryable();
            if (warehouseId.HasValue) q = q.Where(s => s.WarehouseId == warehouseId.Value);
            if (!string.IsNullOrWhiteSpace(status)) q = q.Where(s => s.Status == status);
            return Ok(await q.OrderByDescending(s => s.OpenedAt).Take(200).ToListAsync());
        }
    }
}
```

- [ ] **Step 4: Hook AddSale (two edits in `Controllers/SalesController.cs`)**

(a) Constructor and field. Replace the constructor signature and add a field. Find:

```csharp
        public SalesController(AppDBContext dbContext, IStockService stockService, IInventoryBatchService inventoryBatchService, ITransactionService transactionService, IDocService docService) : base(dbContext)
```

Change to:

```csharp
        private readonly IBusinessEventPublisher _events;
        public SalesController(AppDBContext dbContext, IStockService stockService, IInventoryBatchService inventoryBatchService, ITransactionService transactionService, IDocService docService, IBusinessEventPublisher events) : base(dbContext)
```

and, inside the constructor body next to the other assignments, add `_events = events;`. First confirm nothing else constructs this controller:

Run: `grep -rn "new SalesController" --include=*.cs . | grep -v "/obj/\|/bin/"`
Expected: no matches.

(b) Attach the shift. In `AddSale`, immediately after the comment line `// Save sale and details` and before `_dbContext.Sales.Add(newSale);`, insert:

```csharp
                var activeShift = await _dbContext.CashShifts.FirstOrDefaultAsync(s =>
                    s.CashierId == userId && s.WarehouseId == newSale.WarehouseId && s.Status == CashShiftStatus.Open);
                if (activeShift != null)
                {
                    newSale.ShiftId = activeShift.Id;
                    newSale.CashierId = userId;
                    newSale.PosTerminal = activeShift.PosTerminal;
                }

```

(c) Publish the event. In `AddSale`, immediately after `await _transactionService.AddTransaction(trans);` and before `scope.Complete();`, insert:

```csharp
                _events.Publish(BusinessEventTypes.SaleCompleted, newSale.WarehouseId, $"s-{newSale.Id}",
                    new { saleId = newSale.Id, newSale.TotalAmount, newSale.PaidAmount, newSale.ChangeDue, newSale.PaymentMethod, newSale.ShiftId, newSale.CashierId },
                    newSale.SaleDate);
                await _dbContext.SaveChangesAsync();

```

Confirm `using GoPosify.Services;` already exists at the top of `SalesController.cs` (it injects `IStockService`, so it does).

- [ ] **Step 5: Build and run all tests**

Run: `dotnet build Retailo.csproj` then `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: build succeeds; all tests pass.

- [ ] **Step 6: Grant the new permissions to the default root role (migration)**

```bash
dotnet ef migrations add GrantCashPermissionsToDefaultRole --project Retailo.csproj
```

The generated migration will be empty (the model did not change). Replace its `Up` and `Down` bodies with:

```csharp
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql(@"
UPDATE Roles
SET Permissions = Permissions + ',Cash.Shift,Cash.ShiftList,AI.Read'
WHERE Id = 1 AND Permissions NOT LIKE '%Cash.Shift,%' AND Permissions NOT LIKE '%Cash.Shift';");
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql(@"
UPDATE Roles
SET Permissions = REPLACE(Permissions, ',Cash.Shift,Cash.ShiftList,AI.Read', '')
WHERE Id = 1;");
        }
```

(New tenants created by `Register` already receive every permission in `GetAllPermissions()`, so only the pre-existing root role needs this.)

- [ ] **Step 7: Apply and commit**

```bash
dotnet ef database update --project Retailo.csproj
dotnet build Retailo.csproj
git add DTO/CashShifts/CashShiftDTOs.cs Controllers/CashShiftsController.cs Controllers/SalesController.cs Helpers/Permissions.cs Migrations/*GrantCashPermissionsToDefaultRole*.cs Migrations/AppDBContextModelSnapshot.cs
git commit -m "feat: cash shift API, permissions, and AddSale shift/event hooks"
```

---

### Task 8: Inventory ledger drift service

**Files (PesoWeb):**
- Create: `Services/LedgerService.cs`
- Modify: `Program.cs` (DI)
- Test: `Retailo.Tests/LedgerServiceTests.cs`

**Interfaces:**
- Consumes: `InventoryTransaction` (`QtyIn`, `QtyOut`, `WarehouseId`, `ProductId`, `VariantId`), `ProductWarehouse` (`Quantity`).
- Produces:
  - `LedgerDriftRow { int WarehouseId, int ProductId, int? VariantId, decimal LedgerBalance, decimal OnHand, decimal Drift }` where `Drift = OnHand - LedgerBalance`
  - `ILedgerService.GetDriftAsync(int? warehouseId, decimal tolerance)` returns only rows where `|Drift| > tolerance`, ordered by `|Drift|` descending.
- Design note (deviation from spec): the spec asked to store `QtyBefore/QtyAfter` on each ledger row. The running balance is derivable from the append-only `QtyIn/QtyOut` rows, so this plan does **not** change the ledger table or its four existing write paths. It adds the stronger check instead: **ledger balance vs on-hand drift**, which answers "the system says 50, the shelf has 42, where did 8 go?". Valid for tenants whose stock is received through purchases (all simulator tenants); a real tenant whose opening quantities were typed directly into the product will show an opening-balance drift.

- [ ] **Step 1: Write the failing tests**

`Retailo.Tests/LedgerServiceTests.cs`:

```csharp
using GoPosify.Models;
using GoPosify.Services;
using Retailo.Tests.Support;
using Xunit;

namespace Retailo.Tests;

public class LedgerServiceTests
{
    private static InventoryTransaction Tx(int wh, int product, decimal qtyIn, decimal qtyOut)
        => new() { WarehouseId = wh, ProductId = product, QtyIn = qtyIn, QtyOut = qtyOut, TransactionType = "test" };

    [Fact]
    public async Task No_drift_when_ledger_equals_on_hand()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        db.InventoryTransactions.Add(Tx(1, 10, 100, 0));
        db.InventoryTransactions.Add(Tx(1, 10, 0, 50));
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 10, Quantity = 50 });
        await db.SaveChangesAsync();

        var rows = await new LedgerService(db).GetDriftAsync(null, 0m);

        Assert.Empty(rows);
    }

    [Fact]
    public async Task Reports_eight_missing_units_for_the_milk_example()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        db.InventoryTransactions.Add(Tx(1, 10, 100, 0));
        db.InventoryTransactions.Add(Tx(1, 10, 0, 50));      // ledger says 50
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 10, Quantity = 42 });   // shelf says 42
        await db.SaveChangesAsync();

        var row = Assert.Single(await new LedgerService(db).GetDriftAsync(null, 0m));

        Assert.Equal(50m, row.LedgerBalance);
        Assert.Equal(42m, row.OnHand);
        Assert.Equal(-8m, row.Drift);
    }

    [Fact]
    public async Task Tolerance_hides_small_drift_and_sorts_largest_first()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        db.InventoryTransactions.Add(Tx(1, 1, 10, 0));
        db.InventoryTransactions.Add(Tx(1, 2, 100, 0));
        db.InventoryTransactions.Add(Tx(1, 3, 100, 0));
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 1, Quantity = 9 });     // drift -1
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 2, Quantity = 90 });    // drift -10
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 3, Quantity = 105 });   // drift +5
        await db.SaveChangesAsync();

        var rows = await new LedgerService(db).GetDriftAsync(null, 2m);

        Assert.Equal(new[] { 2, 3 }, rows.Select(r => r.ProductId).ToArray());
    }

    [Fact]
    public async Task On_hand_with_no_ledger_rows_is_reported_as_drift()
    {
        await using var db = new TestAppDbContext(TestAppDbContext.NewDbName(), 5);
        db.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 7, Quantity = 12 });
        await db.SaveChangesAsync();

        var row = Assert.Single(await new LedgerService(db).GetDriftAsync(null, 0m));

        Assert.Equal(0m, row.LedgerBalance);
        Assert.Equal(12m, row.Drift);
    }

    [Fact]
    public async Task Warehouse_filter_and_tenant_isolation_apply()
    {
        var name = TestAppDbContext.NewDbName();
        await using (var t5 = new TestAppDbContext(name, 5))
        {
            t5.InventoryTransactions.Add(Tx(1, 10, 10, 0));
            t5.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 1, ProductId = 10, Quantity = 5 });
            t5.InventoryTransactions.Add(Tx(2, 10, 10, 0));
            t5.ProductWarehouses.Add(new ProductWarehouse { WarehouseId = 2, ProductId = 10, Quantity = 5 });
            await t5.SaveChangesAsync();
        }

        await using var asTenant5 = new TestAppDbContext(name, 5);
        await using var asTenant6 = new TestAppDbContext(name, 6);

        Assert.Equal(2, (await new LedgerService(asTenant5).GetDriftAsync(null, 0m)).Count);
        Assert.Single(await new LedgerService(asTenant5).GetDriftAsync(2, 0m));
        Assert.Empty(await new LedgerService(asTenant6).GetDriftAsync(null, 0m));
    }
}
```

- [ ] **Step 2: Run to confirm failure**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter LedgerServiceTests`
Expected: build FAIL (`LedgerService` not defined).

- [ ] **Step 3: Implement**

`Services/LedgerService.cs`:

```csharp
using GoPosify.Data;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Services;

public sealed class LedgerDriftRow
{
    public int WarehouseId { get; set; }
    public int ProductId { get; set; }
    public int? VariantId { get; set; }
    public decimal LedgerBalance { get; set; }
    public decimal OnHand { get; set; }
    public decimal Drift { get; set; }   // OnHand - LedgerBalance; negative = stock missing vs the ledger
}

public interface ILedgerService
{
    Task<List<LedgerDriftRow>> GetDriftAsync(int? warehouseId, decimal tolerance);
}

public sealed class LedgerService : ILedgerService
{
    private readonly AppDBContext _db;

    public LedgerService(AppDBContext db)
    {
        _db = db;
    }

    public async Task<List<LedgerDriftRow>> GetDriftAsync(int? warehouseId, decimal tolerance)
    {
        var ledger = await _db.InventoryTransactions.AsNoTracking()
            .Where(t => !warehouseId.HasValue || t.WarehouseId == warehouseId.Value)
            .GroupBy(t => new { t.WarehouseId, t.ProductId, t.VariantId })
            .Select(g => new { g.Key.WarehouseId, g.Key.ProductId, g.Key.VariantId, Balance = g.Sum(t => t.QtyIn - t.QtyOut) })
            .ToListAsync();

        var onHand = await _db.ProductWarehouses.AsNoTracking()
            .Where(p => !warehouseId.HasValue || p.WarehouseId == warehouseId.Value)
            .Select(p => new { p.WarehouseId, p.ProductId, p.VariantId, p.Quantity })
            .ToListAsync();

        var rows = new Dictionary<(int, int, int?), LedgerDriftRow>();

        foreach (var l in ledger)
        {
            rows[(l.WarehouseId, l.ProductId, l.VariantId)] = new LedgerDriftRow
            {
                WarehouseId = l.WarehouseId, ProductId = l.ProductId, VariantId = l.VariantId, LedgerBalance = l.Balance
            };
        }

        foreach (var p in onHand)
        {
            var key = (p.WarehouseId, p.ProductId, p.VariantId);
            if (!rows.TryGetValue(key, out var row))
            {
                row = new LedgerDriftRow { WarehouseId = p.WarehouseId, ProductId = p.ProductId, VariantId = p.VariantId };
                rows[key] = row;
            }

            row.OnHand += p.Quantity;
        }

        foreach (var r in rows.Values)
        {
            r.Drift = r.OnHand - r.LedgerBalance;
        }

        return rows.Values
            .Where(r => Math.Abs(r.Drift) > tolerance)
            .OrderByDescending(r => Math.Abs(r.Drift))
            .ToList();
    }
}
```

- [ ] **Step 4: Register in DI**

In `Program.cs`, after `ICashShiftService`:

```csharp
builder.Services.AddScoped<ILedgerService, LedgerService>();
```

- [ ] **Step 5: Run tests**

Run: `dotnet test Retailo.Tests/Retailo.Tests.csproj --filter LedgerServiceTests`
Expected: `Passed: 5`.

- [ ] **Step 6: Commit**

```bash
git add Services/LedgerService.cs Program.cs Retailo.Tests/LedgerServiceTests.cs
git commit -m "feat: inventory ledger vs on-hand drift service"
```

---

### Task 9: Sim read API (`/api/ai/*`)

**Files (PesoWeb):**
- Create: `Controllers/AiController.cs`

**Interfaces:**
- Consumes: `BusinessEvents`, `CashShifts`, `ILedgerService`, permission `AI.Read`.
- Produces (all `GET`, require `AI.Read`, tenant-scoped by the existing query filter):
  - `api/ai/events?afterId=0&take=500&simRunId=` -> `{ events: [{ id, eventType, warehouseId, referenceNo, simRunId, occurredAt, payload }], nextAfterId }` (take capped at 1000; ordered by id ascending so a client can poll with `afterId = nextAfterId`)
  - `api/ai/cash-shifts?warehouseId=&closedOnly=true` -> shifts with expected, actual and variance
  - `api/ai/ledger-drift?warehouseId=&tolerance=0` -> `LedgerDriftRow[]`

- [ ] **Step 1: Add the controller**

`Controllers/AiController.cs`:

```csharp
using System.Text.Json;
using GoPosify.Data;
using GoPosify.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GoPosify.Controllers
{
    // Read-only, structured data for the simulator and the AI layer. Never mutates business data.
    [Route("api/[controller]/[action]")]
    [ApiController]
    [Authorize]
    public class AiController : BaseController
    {
        private readonly ILedgerService _ledger;

        public AiController(AppDBContext dbContext, ILedgerService ledger) : base(dbContext)
        {
            _ledger = ledger;
        }

        // GET: api/ai/events?afterId=0&take=500&simRunId=run-42
        [HttpGet("~/api/ai/events")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> Events(long afterId = 0, int take = 500, string simRunId = null)
        {
            take = Math.Clamp(take, 1, 1000);

            var q = _dbContext.BusinessEvents.AsNoTracking().Where(e => e.Id > afterId);
            if (!string.IsNullOrWhiteSpace(simRunId))
            {
                q = q.Where(e => e.SimRunId == simRunId);
            }

            var rows = await q.OrderBy(e => e.Id).Take(take).ToListAsync();
            var events = rows.Select(e => new
            {
                e.Id,
                e.EventType,
                e.WarehouseId,
                e.ReferenceNo,
                e.SimRunId,
                e.OccurredAt,
                Payload = string.IsNullOrWhiteSpace(e.PayloadJson) ? (JsonElement?)null : JsonDocument.Parse(e.PayloadJson).RootElement.Clone()
            }).ToList();

            return Ok(new { events, nextAfterId = rows.Count > 0 ? rows[^1].Id : afterId });
        }

        // GET: api/ai/cash-shifts?warehouseId=1&closedOnly=true
        [HttpGet("~/api/ai/cash-shifts")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> CashShifts(int? warehouseId, bool closedOnly = true)
        {
            var q = _dbContext.CashShifts.AsNoTracking().AsQueryable();
            if (warehouseId.HasValue) q = q.Where(s => s.WarehouseId == warehouseId.Value);
            if (closedOnly) q = q.Where(s => s.Status == CashShiftStatus.Closed);

            var shifts = await q.OrderByDescending(s => s.OpenedAt).Take(1000)
                .Select(s => new { s.Id, s.WarehouseId, s.CashierId, s.OpenedAt, s.ClosedAt, s.OpeningCash, s.ExpectedCash, s.ActualCash, s.Variance, s.Status })
                .ToListAsync();
            return Ok(shifts);
        }

        // GET: api/ai/ledger-drift?warehouseId=1&tolerance=0
        [HttpGet("~/api/ai/ledger-drift")]
        [Authorize(Policy = "AI.Read")]
        public async Task<IActionResult> LedgerDrift(int? warehouseId, decimal tolerance = 0m)
        {
            return Ok(await _ledger.GetDriftAsync(warehouseId, tolerance));
        }
    }
}
```

Routing note: the `~/` prefix makes each attribute route absolute, so it replaces the controller-level `api/[controller]/[action]` template. That gives the kebab-case paths `api/ai/cash-shifts` and `api/ai/ledger-drift` (the controller name is `Ai`, which would otherwise produce `api/Ai/CashShifts`).

- [ ] **Step 2: Build**

Run: `dotnet build Retailo.csproj`
Expected: success.

- [ ] **Step 3: Verify routes against the running app**

Start the app (same command as Task 3 Step 1). Fetch `http://localhost:5061/swagger/v1/swagger.json` and confirm the paths `/api/ai/events`, `/api/ai/cash-shifts`, `/api/ai/ledger-drift` exist and that `/api/Ai/Events` style duplicates do not.

Run: `powershell -Command "(Invoke-RestMethod http://localhost:5061/swagger/v1/swagger.json).paths.PSObject.Properties.Name | Where-Object { $_ -match 'api/ai' }"`
Expected: exactly the three absolute paths.

- [ ] **Step 4: Commit**

```bash
git add Controllers/AiController.cs
git commit -m "feat: read-only /api/ai events, cash-shifts and ledger-drift endpoints"
```

---

### Task 10: End-to-end API smoke, production script, and patch export

**Files:**
- Create (hackathon repo): `pesoweb-additions/smoke/cash-shift-smoke.ps1`, `pesoweb-additions/README.md`, `pesoweb-additions/patches/*.patch`
- Create (PesoWeb): `scripts/20261003_sim_foundation.sql`
- Modify (hackathon repo): `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md` (deviation note)

**Interfaces:**
- Consumes: Task 3 helpers (`New-SimTenant`, `Invoke-PesoApi`), all Task 4-9 endpoints.
- Produces: a green end-to-end proof, an idempotent SQL deployment script, and an applyable patch set for the public repo.

- [ ] **Step 1: Write the smoke script**

`pesoweb-additions/smoke/cash-shift-smoke.ps1`:

```powershell
param([string] $BaseUrl = 'http://localhost:5061')
. "$PSScriptRoot\common.ps1"

function Assert-Equal($actual, $expected, $what) {
    if ([decimal]$actual -ne [decimal]$expected) { throw "FAIL $what : expected $expected, got $actual" }
    Write-Host "OK   $what = $actual"
}

$run = "smoke-" + [guid]::NewGuid().ToString('N').Substring(0, 8)
$t = New-SimTenant -BaseUrl $BaseUrl -Prefix 'cashsmoke'
$wh = $t.WarehouseId

# Cashier opens a shift with 1000 float
$shift = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Open' -SimRun $run `
    -Body @{ warehouseId = $wh; posTerminal = 'POS-01'; openingCash = 1000 }
Write-Host "Opened shift $($shift.id)"

# A second open shift for the same cashier must be refused
$refused = $false
try {
    Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Open' -SimRun $run `
        -Body @{ warehouseId = $wh; posTerminal = 'POS-02'; openingCash = 50 } | Out-Null
} catch { $refused = $true }
if (-not $refused) { throw 'FAIL second open shift should have been refused' }
Write-Host 'OK   second open shift refused'

# Cash in 200, cash out 0, count 1150 -> expected 1200, variance -50
Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/AddMovement' -SimRun $run `
    -Body @{ shiftId = $shift.id; movementType = 'CashIn'; amount = 200; reason = 'float top-up' } | Out-Null

$current = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/CashShifts/Current?warehouseId=$wh"
Assert-Equal $current.summary.expectedCash 1200 'expected cash before close'

$closed = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method POST -Path '/api/CashShifts/Close' -SimRun $run `
    -Body @{ shiftId = $shift.id; actualCash = 1150; note = 'smoke' }
Assert-Equal $closed.expectedCash 1200 'closed expected cash'
Assert-Equal $closed.variance -50 'closed variance'

# Events for this run must include CashOpened and CashClosed
$ev = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/events?simRunId=$run"
$types = @($ev.events | ForEach-Object { $_.eventType })
if (($types -notcontains 'CashOpened') -or ($types -notcontains 'CashClosed')) { throw "FAIL events missing, got: $($types -join ',')" }
Write-Host "OK   events tagged $run : $($types -join ', ')"

# Shift shows up in the AI read API with its variance
$shifts = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/cash-shifts?warehouseId=$wh&closedOnly=true"
$mine = @($shifts) | Where-Object { $_.id -eq $shift.id }
Assert-Equal $mine.variance -50 'ai/cash-shifts variance'

# Ledger drift endpoint answers (empty for a fresh tenant)
$drift = Invoke-PesoApi -BaseUrl $BaseUrl -Token $t.Token -Method GET -Path "/api/ai/ledger-drift?warehouseId=$wh"
Write-Host "OK   ledger-drift rows: $(@($drift).Count)"

Write-Host 'ALL CHECKS PASSED'
```

- [ ] **Step 2: Run it against the running app**

Start PesoWeb (Task 3 Step 1), then:
Run: `powershell -File pesoweb-additions/smoke/cash-shift-smoke.ps1`
Expected: every line starts with `OK` and the last line is `ALL CHECKS PASSED`.

If a check fails, fix the PesoWeb code (not the script) unless the script is wrong. A likely cause: the new tenant's cashier lacks a `UserWarehouses` row, which makes `Open` return "You do not have access to this branch." If so, check how `Register` assigns the owner to the default warehouse and record the finding in `Docs/onboarding-contract.md`; the fix, if needed, is a small addition to the registration path, and must be reported to the user before making it.

- [ ] **Step 3: Run the full unit-test suite one more time**

Run (PesoWeb repo): `dotnet test Retailo.Tests/Retailo.Tests.csproj`
Expected: all pass: harness 1, publisher 4, cash shift 13, ledger 5 (23 total).

- [ ] **Step 4: Generate the idempotent production script**

```bash
cd /d/git/Retailo_v1
dotnet ef migrations script --idempotent --project Retailo.csproj -o scripts/20261003_sim_foundation.sql
```

Open the file and confirm that it only contains the three new migrations' statements wrapped in `IF NOT EXISTS (SELECT * FROM __EFMigrationsHistory ...)` guards (earlier migrations will also appear as guarded no-ops; that is expected for `--idempotent`). Commit it.

```bash
git add scripts/20261003_sim_foundation.sql
git commit -m "chore: idempotent deployment script for sim foundation migrations"
```

- [ ] **Step 5: Export the patch set into the hackathon repo**

```bash
cd /d/git/Retailo_v1
mkdir -p /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches
git format-patch main..Retail_MissionCommerceAI -o /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches
ls /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas/pesoweb-additions/patches
```

Expected: one `.patch` file per commit on the branch (about 10). Review each `.patch` for secrets or unrelated files before committing it to the public repo: `grep -il "password\|secret\|connectionstring" pesoweb-additions/patches/*.patch` should list only files where the match is a test fixture or the smoke-test strings, never a real credential. If a real credential appears, stop and report.

- [ ] **Step 6: Write the README for the patches**

`pesoweb-additions/README.md`:

```markdown
# PesoWeb additions for Sim.PesoWeb

PesoWeb (the system under test) is a separate product repository. This folder carries only the **additive** changes made for the hackathon, so the work is visible and reproducible.

## What the patches add
- Business event outbox (`BusinessEvent`) tagged with the `X-Sim-Run` header
- Cashier shift and cash drawer (`CashShift`, `CashMovement`), expected cash and variance
- Nullable `ShiftId / CashierId / PosTerminal` on `Sale`; audit context columns on `AuditLog`
- Inventory ledger vs on-hand drift service
- Read-only `/api/ai/events`, `/api/ai/cash-shifts`, `/api/ai/ledger-drift`
- xUnit test project `Retailo.Tests` (23 tests)

## Apply
    git checkout -b Retail_MissionCommerceAI
    git am pesoweb-additions/patches/*.patch
    dotnet test Retailo.Tests/Retailo.Tests.csproj
    dotnet ef database update            # local/dev database
    # production: run scripts/20261003_sim_foundation.sql (idempotent)

## Smoke
With PesoWeb running on http://localhost:5061:
    powershell -File pesoweb-additions/smoke/cash-shift-smoke.ps1
```

- [ ] **Step 7: Record the spec deviations**

In `docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md`, section 4, directly under the table, add:

```markdown
**Implementation notes (Plan 1):**
- Item 3 is implemented as a derived ledger-vs-on-hand drift check (`/api/ai/ledger-drift`) instead of storing `QtyBefore/QtyAfter` on each ledger row. The ledger is append-only, so the running balance is derivable without touching the four existing write paths. Valid for tenants stocked through purchases (all simulator tenants).
- Item 8's read API uses the normal JWT and a new `AI.Read` permission rather than a separate API key.
- Cash refunds in the expected-cash formula come from `CashMovement` rows of type `Refund`; sale returns create them automatically in Plan 2.
- `Sale` gains nullable `ShiftId`, `CashierId`, `PosTerminal`; `AuditLog` gains `WarehouseId`, `ReferenceNo`, `BeforeValue`, `AfterValue`.
```

- [ ] **Step 8: Commit in the hackathon repo**

```bash
cd /d/git/AMD/hackathon_amd_act3/MissionCommerceAI_by_eVo.Ninjas
git add pesoweb-additions/smoke/cash-shift-smoke.ps1 pesoweb-additions/README.md pesoweb-additions/patches Docs/superpowers/specs/2026-10-03-sim-pesoweb-missioncommerce-design.md
git commit -m "P1a: cash-shift smoke, sim-foundation patches, spec implementation notes"
```

---

## Exit criteria for Plan 1

- `Docs/amd-smoke-test.md` shows a ROCm GPU and a vLLM reply with real numbers.
- `Docs/onboarding-contract.md` documents the verified Register-to-product chain, with any broken link named.
- 23 xUnit tests pass; `cash-shift-smoke.ps1` prints `ALL CHECKS PASSED`.
- A cashier can open a shift, record cash movements, close with a counted amount, and the variance and events are visible through `/api/ai/*`.
- `AddSale` attaches the open shift and publishes `SaleCompleted`.
- Patches and a production SQL script exist and contain no secrets.

## Self-review (against the spec)

**Spec coverage.**
- Phase 1 item 1 (cash shift and drawer, formula, variance): Tasks 5-7.
- Item 8 (business event stream, Sim API, `X-Sim-Run`): Tasks 4, 9.
- Item 3 (ledger and audit hardening): Task 5 (audit columns) and Task 8 (drift). Deviation recorded in Task 10 Step 7.
- P0 (ADP, ROCm, vLLM smoke, onboarding chain, tier limits check): Tasks 1, 3. Tier limits are confirmed present in PesoWeb (`GetTierLimitsForTenantAsync`, `AddWarehouse` enforcing `BranchLimit`); Task 3 Step 4 exercises the refusal.
- Items 2, 4, 5, 6, 7: intentionally deferred to Plan 2.
- Sim, AI, UI, Quick Sim, scenarios: Plans 3-5.

**Placeholder scan.** No TBD/TODO. Two steps are investigative by nature and say so with exact commands and acceptance criteria: Task 3 Step 5 (document the remaining onboarding links) and Task 10 Step 2's contingency for the warehouse-access finding.

**Type consistency.** `BusinessEventTypes.CashOpened/CashClosed/SaleCompleted`, `IBusinessEventPublisher.Publish(eventType, warehouseId, referenceNo, payload, occurredAt)`, `CashShiftStatus`, `CashMovementType.All`, `CashShiftCalculator.ExpectedCash/Variance`, `ICashShiftService` (Open/AddMovement/Summarize/Close), `ILedgerService.GetDriftAsync(int?, decimal)` and DTO names are used identically in tests, services, controllers and the smoke script.

# Folder structure: MissionCommerce AI and Sim.PesoWeb

The project lives in two repositories that fit together:

| Repository | Folder on this PC | What it holds |
|---|---|---|
| **Hackathon repo** (`MissionCommerceAI_by_eVo.Ninjas`) | `D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas` | The AI, the simulator, the dashboards, the docs and results, and patches that describe our changes to PesoWeb |
| **PesoWeb worktree** (`Retailo_v1_mission`, branch `Retail_MissionCommerceAI`) | `D:\git\Retailo_v1_mission` | PesoWeb itself (the POS and ERP: back end and Angular front end) with our additions, plus a copy of the AI source in `mission-ai/` |

How they talk: the **simulator** (`sim/`) acts as shoppers and staff and calls PesoWeb's real API. The **AI** (`ai/`) reads PesoWeb data through `/api/ai/*`, makes proposals, and PesoWeb applies its rules, approvals and on/off switches before anything changes.

```
Simulator (sim/)  --->  PesoWeb API (Controllers/, Services/)  <---  AI agent (ai/ + sim/simpeso/agent_service.py)
                              |                                              |
                        SQL Server                                 proposals back to PesoWeb
                              |
                  Angular screens (ClientApp/): Approval Center, AI Control, Intelligence Hub
```

---

## 1. Hackathon repo

```
MissionCommerceAI_by_eVo.Ninjas/
├── readme.md, LICENSE, Dockerfile, docker-compose.yml, .gitignore
├── ai/                          The AI layer (Python, no PesoWeb code)
│   ├── missionai/               The AI itself
│   │   ├── price_advisor.py       list-price advice (learns price sensitivity; rival-price cap)
│   │   ├── optimizer.py           markdown (clearance) price choice
│   │   ├── demand.py              demand estimates
│   │   ├── detectors.py           loss-prevention detectors
│   │   ├── behavior_shift.py      detects changes in shopper behaviour
│   │   ├── replenish.py           AI Replenish: what to reorder and how much
│   │   ├── missions.py            AI Customer Mission: what shoppers were trying to do
│   │   ├── explain.py             plain-language explanations
│   │   ├── price_test.py          price experiments
│   │   ├── recorder.py, agent.py  decision log and the agent loop
│   ├── tests/                   Unit tests (134)
│   └── smoke/                   Quick checks for the AMD GPU server
├── sim/                         The simulator (Python)
│   ├── simpeso/                 Library
│   │   ├── driver.py              calls PesoWeb's API (register, products, sales, hub, replenish...)
│   │   ├── world.py, runner.py    the simulated shop world and the day loop
│   │   ├── customers.py, archetypes.py, behavior.py   simulated shoppers
│   │   ├── perishables.py, verticals.py, incidents.py   products, expiry, staged problems
│   │   ├── agent_service.py       the agent runner (polls PesoWeb, does the AI's jobs)
│   │   ├── approver.py            simulated approver for the Approval Center
│   │   ├── price_run.py, pricetest.py, equalize.py   price proposals and fair twin worlds
│   │   ├── competitors.py, mission_sim.py   simulated rival prices and basket feeds
│   │   ├── calibration.py, scoring.py, proof.py, story.py, quicksim.py, rng.py, ai_hook.py
│   │   └── data/                  real-catalog and calibration data
│   ├── scripts/                 Things you run
│   │   ├── showcase*.py, aa_check.py        PesoProfit showcase and the A/A fairness check
│   │   ├── *_check.py                       live checks (hub 22, extras 20, background 6, AI control 23, approval center 17)
│   │   ├── hub_demo_seed.py, competitor_feed.py, mission_run.py, price_advice.py, ...
│   ├── tests/                   Unit tests (167)
│   └── runs/                    Run output and CREDENTIALS.txt (git-ignored, never copy it)
├── ui/
│   ├── dashboard/               The AI dashboard (index.html, day.html, reports.html)
│   ├── hub/index.html           One-page explainer of the Intelligence Hub
│   ├── demo/                    capture.mjs (screenshot tool), start-demo.ps1 (starts everything)
│   └── prototype/               Early design mock-ups
├── pesoweb-additions/           What we changed in PesoWeb, as patches and notes
│   ├── README.md                What each plan added and how to apply it
│   ├── patches/plan1 ... plan12   git patches, one folder per plan
│   ├── smoke/, tools/           Smoke tests and helper tools (migration cleanup)
├── results/                     Showcase results (JSON and exports)
├── Docs/                        Documentation
│   ├── demo/DEMO-GUIDE.md       Screen-by-screen guide; demo/screens/ holds the screenshots
│   ├── intelligent-hub-design.md, ai-settings-and-pesoprofit-map.md
│   ├── showcase-results.md, amd-setup-guide.md, problem-statement.md
│   ├── superpowers/             Plans and specs
│   └── folder-structure.md      This file
├── amd-hackathon-act3-requirements/   The hackathon's requirement documents
└── demo/                        Demo material
```

## 2. PesoWeb worktree (`Retailo_v1_mission`)

PesoWeb is an ASP.NET Core (.NET 9) back end with an Angular 16 front end and SQL Server. Folders marked **(ours)** hold the additions made for this project; the rest is PesoWeb's own.

```
Retailo_v1_mission/
├── Retailo.csproj, Retailo.sln, Program.cs, appsettings*.json
├── Controllers/                 The web API, one file per area
│   ├── AiControlController.cs     (ours) AI Control and the whole Intelligence Hub API (/api/ai/control, /hub/*, /replenish, /missions, /competitor-*, /channel)
│   ├── AiController.cs            (ours) data the AI reads and writes (/api/ai/*)
│   ├── PricingController.cs       list-price changes and the Approval Center
│   ├── SalesController, PurchasesController, InventoryController, StockCountsController, ExpiryController,
│   │   CashShiftsController, ExceptionsController, AccountingController, ReportsController, PeopleController,
│   │   HRMController, AuthController, SettingsController, TenantsController, GroupController, SyncController, ...
├── Services/                    Business logic
│   ├── AiControlService.cs        (ours) the six AI features, on/off, branch settings
│   ├── ApprovalQueueService.cs, ApprovalLanes.cs, ListPriceService.cs, ListPriceGuardrails.cs   (ours) approvals and margin rules
│   ├── HubMetricsService.cs, HubRuleService.cs, HubTaskService.cs, HubInsightServices.cs,
│   │   HubChannelService.cs, HubBackgroundService.cs, ReplenishService.cs, GroupOverviewService.cs   (ours) Intelligence Hub
│   ├── AiImpactService.cs         (ours) AI Impact: before/after and AI branch vs control branch
│   ├── MarkdownPricingService.cs, MarkdownGuardrails.cs, MarkdownService.cs   markdown (clearance) pricing
│   ├── StockService, InventoryBatchService, ExpiryService, StockCountService, ReceivingService,
│   │   CashShiftService, ExceptionService, LedgerService, TransactionService, SyncService, ...
├── Models/                      Database entities (one file per entity or group)
│   ├── AiControl.cs, HubRules.cs, HubExtras.cs, Replenish.cs, PriceChange.cs, PricingPolicy.cs   (ours)
│   └── Product, Sale, Purchase, Warehouse (branch), User, Role, ... (PesoWeb's own)
├── Migrations/                  EF Core migrations (ours: ApprovalCenter, AiControl, AiBranchSettings, HubRules..., Hub assignees/regions/...)
├── Data/                        AppDBContext (tenant filter on every query)
├── DTO/, Helpers/, Pages/       Request/response shapes, helpers, server pages
├── ClientApp/                   Angular front end
│   └── src/app/
│       ├── ai/aicontrol/          (ours) AI Control screen (/ai/control)
│       ├── ai/aihub/              (ours) Intelligence Hub screen (/ai/hub)
│       ├── pricing/approvalcenter/  (ours) Approval Center (/pricing/approvals)
│       ├── sales, purchases, inventory, people, hrm, reports, settings, dashboard, accounting, mobile, ...
│       └── app.module.ts, app.component.html   routes and the menu
├── Retailo.Tests/               Back-end tests (245 pass); ours: ApprovalCenter, AiControl, Hub* tests
├── scripts/                     SQL scripts for each migration (idempotent) and smoke checklists
├── mission-ai/                  (ours) a copy of the hackathon repo's ai/, sim/, ui/, results/ and key docs, so everything is in one place
├── docs/, DATABASE/, DataMigrateMultiTenants/, Integration_API_SYNC/, LandingPage/, wwwroot/, AppFiles/
└── bin/, obj/, PUBLISH1*, TEMP/   Build output and scratch (not source)
```

## 3. Where to find what

| I want to... | Look here |
|---|---|
| Change how the AI prices, reorders or reads missions | `ai/missionai/` |
| Change the simulated shoppers or shop | `sim/simpeso/` |
| Add or change an API endpoint | `Controllers/AiControlController.cs`, `PricingController.cs` |
| Change a rule, approval check or hub number | `Services/` (`HubMetricsService.cs` holds the number definitions) |
| Change a screen | `ClientApp/src/app/ai/`, `ClientApp/src/app/pricing/approvalcenter/` |
| Add a database table | `Models/`, then a migration in `Migrations/` and a script in `scripts/` |
| Start the demo | `ui/demo/start-demo.ps1` |
| See screenshots and the click-through | `Docs/demo/DEMO-GUIDE.md` |
| Check everything works | `dotnet test Retailo.Tests`; `python -m unittest discover -s tests -t .` inside `sim/` and `ai/`; the `*_check.py` live scripts |

`mission-ai/` is a copy: edit the hackathon repo first, then refresh the copy.

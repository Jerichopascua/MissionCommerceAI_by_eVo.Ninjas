# AI settings today, and the PesoProfit one-pager against what is built

Recorded 2026-10-05 before the showcase run. Values were read from the code and from the dev database, not from memory.

## 1. Backup taken first

| What | Where |
|---|---|
| `PesoWeb_MissionDev` (all simulated tenants, 125 MB) | `C:\Users\Lito\PesoWeb_Backups\PesoWeb_MissionDev_20261005_1553.bak` (verified) |
| `PesoWeb_V2_Real` (restored copy of your Sept 20 backup, 20 MB) | `C:\Users\Lito\PesoWeb_Backups\PesoWeb_V2_Real_20261005_1553.bak` (verified) |
| Private run files (credentials, real catalog, calibration, ledgers) | `C:\Users\Lito\PesoWeb_Backups\sim_runs_20261005.zip` |
| Code | git tag `pre-showcase` in the hackathon repo and in the PesoWeb worktree |
| Your original backups | untouched in `D:\git\Retailo_v1\DATABASE` |

Restore a database backup with `RESTORE DATABASE <name> FROM DISK=N'<file>' WITH REPLACE` (stop the PesoWeb app first).

## 2. Current AI settings

### Owner's rules inside PesoWeb (the agent cannot change them)

| Setting | Meaning | Set by |
|---|---|---|
| Autonomy mode: `Autonomous` / `Approval` / `Off` | Off = nothing is ever applied; Approval = every markdown waits for a human | per tenant, `PUT /api/Pricing/Policy` |
| Hard margin floor | price never below cost + this %, cannot be waived | per tenant |
| Soft margin floor | below this needs approval | per tenant |
| Max discount % | never deeper than this | per tenant |
| Max changes per product per hour | rate limit | per tenant |
| A tenant with no policy row | behaves as **Off** | default |

What is actually set in the dev database now (209 tenants with a policy row, 51 without): 115 tenants Autonomous with hard 0 / soft 5 / max 50 / 6 per hour (the proof runs and the real-catalog world), 25 Autonomous 5 / 10 / 50 / 6 (concept demo and customer story), 15 Autonomous 10 / 20 / 50 / 6 (first experiments), 3 Autonomous 5 / 15 / 50 / 3, 11 Off. The 51 tenants without a row (the original and early smoke tenants) are Off.

### The markdown agent and optimizer (`ai/missionai`)

| Setting | Value |
|---|---|
| Discount ladder | 0, 10, 20, 30, 40, 50 % |
| Only acts if the gain beats doing nothing by | at least 1 peso and 1% |
| Batches considered | status ExpiringSoon or Critical, 1 to 3 days left, stock above 0 |
| Objective | expected revenue minus sunk cost (margin on units sold minus write-off of leftovers), FEFO queue ahead of the batch respected |
| How often it looks | each tick: hourly in the simulator runs, every 15 minutes in the customer story |
| Clearance window (owner choice, agent setting) | no markdown before 20:30 in the customer story; none in the other runs |
| Predictions | recorded before acting; one per batch; scored against what sold |
| On a refusal (422) or pending approval (202) | logged with PesoWeb's code, never retried at a lower price |

### The demand model

| Setting | Value |
|---|---|
| Starting guess of price sensitivity (log-price slope) | -1.5 in the demos and customer story, -1.3 in the simulator runs |
| Strength of that guess | 3.0 (pulls estimates toward it when data is thin) |
| Allowed range of the slope | -6.0 to +0.5 |
| Hour-of-day pattern | learned from baseline sales; flat prior mixed in: 2% (simulator runs), 30% (customer story, because list-price sales under-show late demand) |
| What it learns from | the shop's own sales at different prices (promo days), 2 baseline days + 4 promo days in the simulator runs, 3 baseline days in the story |

### Finding what the POS cannot see

| Setting | Value |
|---|---|
| Counting budget | SKUs counted per branch: 4 or 8 in the runs (coverage 80% / 100%) |
| Ranking | unreported deliveries first (weight 1.0), then value and speed of sale (weight 0.15) |
| A count counts as a finding if short by | at least 1 unit |
| First purchase of a SKU | treated as opening stock, not a delivery |
| Cash incident match tolerance in scoring | 10 pesos |

### Explainer

Template sentence by default. A vLLM endpoint is used only if `VLLM_URL` is set; not yet exercised on AMD. It never decides anything.

### Customers and the simulated world

| Setting | Value |
|---|---|
| Customer actors | 40 per neighbourhood, evening 17:00 to 22:00 in 15-minute steps, patience up to 2.5 h |
| Real-data calibration | opt-in; weight 0.5 on the real hour profile; basket scale 0.496 (real 2.0 lines per sale against 3.9) |
| Real catalog world `real1` | 5 companies, 493 real products each, policy Autonomous 0 / 5 / 50 / 6, non-expiry |
| Simulated profiles | `smoke`: 2 branches per company, 8-product generated catalog; `starter`: 4 branches, 30 products |

Not settings but worth knowing: shoppers' true price response is the simulator's own hidden assumption; the AI never sees it.

## 2b. Where the owner switches the AI on and off (added 2026-10-05)

The AI Control screen in PesoWeb (`/ai/control`) lists the six AI products with a switch each, their build state, and a Run now button for the ones that can run. With AI Pricing off, PesoWeb refuses what the AI proposes, so it cannot change a price even if the agent keeps running. This is separate from "Pricing autonomy" (Off, Approval, Autonomous) in the Approval Center settings, which says what happens to proposals that are accepted. A company with no saved switch has every feature on. The agent is a separate program (`python -m simpeso.agent_service`); Run now only works while it is running.

## 2c. PesoProfit run on the real catalog (2026-10-06)

The full flow (AI Pricing run, Approval Center, simulated approver, markdown agent) ran on the real catalog, one day and then ten more days against a no-AI twin. On the real thin margins the AI was behind the no-AI world on all 10 days (net about -0.5k to -1.3k pesos a day, revenue down). Details, reasons and next steps: `Docs/showcase-results.md`. The generated-shop proof (-58% waste) is a separate result.

## 3. The PesoProfit one-pager against what is built

| One-pager says | Built today? | Evidence or gap |
|---|---|---|
| Ingest product expiry timelines | **Yes** | expiry risk and all-batches feeds; the agent reads days left per batch |
| Ingest inventory and rate of sale per SKU and store | **Yes** | stock, batch and sales-ledger feeds; learned sales rate and hour pattern |
| Ingest **competitor prices** at store level | **No** | the design called for a simulated competitor feed; not built |
| Agents decide and execute continuously through the day | **Yes** | hourly (or 15-minute) ticks through the real pricing API |
| Hard and soft margin thresholds | **Yes** | enforced inside PesoWeb on every markdown |
| Store-level **waste reduction targets** | **No** | there is no waste-target setting; waste is reported, not targeted |
| Alignment with strategic trading priorities | **No** | not modelled |
| Price change store by store, SKU by SKU, moment by moment | **Yes** | per batch, per branch; the POS charges it at sale time |
| Push to **electronic shelf labels, e-commerce, picker systems** | **No** | PesoWeb emits a `PriceChanged` event, but no shelf-label, e-commerce or picker channel exists (the design's `channels` module was never built) |
| Reduced shrink and waste | **Measured** | -58% waste against doing nothing over 5 seeds; tied with a fixed 30%-off rule |
| Protected margins | **Yes** | floors enforced; thin real margins limit what is allowed |
| Real-time agility | **Partly** | intra-day ticks work; reaction to competitors does not exist |

## 4. Proposed showcase order, "PesoProfit: Agentic Retail in Action"

1. **One shop, one decision (1 minute):** `python demo/concept_demo.py`. Expiring milk, the agent's decision table, PesoWeb applies a safe price and refuses an unsafe one.
2. **The same idea on real prices:** Alma Store's real products in the `real1` group, with perishable lots added to chosen food items, so the agent works on real costs and thin real margins (needs your pick of which products are perishable).
3. **Customers who think and learn:** the chicken story, with Marco's diary and what the system saw.
4. **Group view:** the day report by company and branch, then the results dashboard (three-way proof, caught vs missed).

Gaps to say out loud on stage: no competitor feed, no shelf-label or e-commerce sync, no waste-target setting, and the AI ties a simple fixed rule in the measured proof.

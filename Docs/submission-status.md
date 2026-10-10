# Submission status: AMD Developer Hackathon Act III, Track 3 "Reinvent Commerce"

Team Evo.Ninjas. Written 2026-10-10. Source of the requirements: `amd-hackathon-act3-requirements/` (04 checklist, 03 AMD rules, 05 judging, 07 schedule).

## 1. Dates (Philippine time)

| When | What |
|---|---|
| Mon Oct 12, 11:00 PM | Kick-off (online build window opens) |
| Tue Oct 13, 12:00 AM | Discord Q&A: **ask whether work started before kick-off counts** (see risk 3) |
| **Sun Oct 18, 10:00 PM** | **End of submissions** |
| Sun Oct 18, 11:00 PM | Live on-stage pitching |

## 2. The checklist, item by item

| Item | Status | Where / what is left |
|---|---|---|
| Project title, short and long description, tags | **Drafted below** | Section 4; paste into the form |
| Track: Track 3 Reinvent Commerce | Done | |
| Cover image | **You** | Pick one from `Graphics_Presentations/` (your untracked folder) |
| Demo video | **To do** | Storyboard `Docs/demo-video-storyboard.md`; record from the real running system, not the prototype. Rehearsal order: `Docs/demo/DEMO-GUIDE.md` |
| Pitch / slides | **You** | Your folder `Graphics_Presentations/` has architecture, process-flow and tech-stack images |
| Problem and intended user | Done in text | `Docs/ai-in-pesoweb-standard-explainer.md`, `Docs/problem-statement.md` |
| **Public GitHub repository** | **You: check it is public** | `github.com/Jerichopascua/MissionCommerceAI_by_eVo.Ninjas`, branch `master` is current as of the last push |
| Working prototype and **application URL** | **Gap (risk 2)** | PesoWeb runs on this PC only. See risk 2 for options |
| **AMD workload meaningful and shown in the demo** | **Not done (risk 1)** | Mandatory. Plan below |
| Prediction logic explained, not LLM-only | Done | Section 3 of the standard explainer; the demand model is a Poisson price-response model fitted on sales |
| Measurable business effect, before and after | Done, modest | `Docs/showcase-results.md`: AI ahead on 10 of 10 test days, gross margin about +8%, from twin worlds with an A/A check |
| Original work, MIT licence | Done | `LICENSE` is MIT |
| No API keys committed | **Check done, one thing to fix (risk 4)** | No keys in committed files. A private-key block is in your uncommitted `Docs/amd-setup-guide.md` |
| Containerised app, README that runs (only for the Evolus prize) | Partly | `Dockerfile` and `docker-compose.yml` exist for the Python side and have never been built; PesoWeb has no container |

## 3. Risks, in order of importance

1. **AMD is mandatory and not yet run.** The rule: a meaningful part of the workload must run on AMD hardware, and it must be part of the working product shown to judges. Plan: one session on the AMD Developer Cloud following `Docs/amd-setup-guide.md` (Parts 2 to 5), recording `rocm-smi`, the Quick Sim run (200,000 simulated shoppers for 28 days on PyTorch/ROCm) and, if time allows, Qwen on vLLM for the explanations. Put the numbers and a screenshot in `Docs/amd-smoke-test.md` and the video. Destroy the server afterwards. Do it by Oct 14 so there are three days of buffer. *An external AI API (Claude, for the hero shoppers) does not count as the AMD part.*
2. **There is no public application URL.** PesoWeb needs SQL Server and .NET, so it is not hosted. Options, cheapest first:
   - (a) Host the static results dashboard and the explainer on GitHub Pages (works from the repo; the page reads `results/*.json`), and show PesoWeb in the video. The honest label is "results dashboard".
   - (b) Run the full stack on the AMD server with Docker (PesoWeb, SQL Server for Linux, Angular build). It is a real day of work and has never been tried.
   - Recommendation: (a), plus a clear "run it locally" README for PesoWeb.
3. **"Built during the event".** Most of this was built before the Oct 12 kick-off. Ask in the Oct 13 Q&A whether pre-existing work is allowed; the answer decides how we word the submission (for example: PesoWeb existed, the AI layer, simulator and hub were built for this hackathon). The git history shows when each part was added.
4. **A private key is in your notes.** `Docs/amd-setup-guide.md` (modified, not committed) contains an SSH private-key block. It is not in any commit and not on GitHub. Delete that block before anyone commits or shares the file, and if the file was shared anywhere, create a new key in the AMD console.
5. **Evidence from real shoppers is thin.** 50 real receipts from one store. The demand check on a public dataset is the fastest fix (see the standard explainer, section 5b).

## 4. Text for the form (edit freely)

**Title:** MissionCommerce AI by Evo.Ninjas: a safe AI co-pilot for a real retail POS

**Short description:** An AI layer for a working retail POS that proposes markdowns, prices, reorders and alerts. The POS enforces margin rules, approvals and on/off switches, and a person decides. Measured against a no-AI control shop.

**Long description:**
Small retailers have the data in their till but not the decisions: short-dated food is thrown away, prices are set by habit, shelves run empty, and cash and stock leak. MissionCommerce AI adds an Intelligent Hub to PesoWeb, a real multi-tenant POS and ERP. It reads sales, stock, expiry, cash and price history and proposes concrete actions: markdowns for stock close to expiry, list-price changes learned from the shop's own sales, reorders that become draft purchase orders, shopper-mission insight, and alerts for unusual activity. Every proposal arrives with its reason, the margin before and after, what rivals charge and a cautious estimate. PesoWeb enforces margin floors, approval lanes, per-company and per-branch AI switches and an audit trail, so the AI only suggests and people stay in control. Predictions come from a transparent statistical demand model, never from a language model alone; a language model only words explanations. We tested it by running two identical simulated shops on the real PesoWeb API, one with the AI and one without, after proving the twins identical with an A/A check: the AI shop was ahead on 10 of 10 test days, about 8% more gross margin with less waste. We report the limits plainly: simulated shoppers, a modest gain on thin margins, and real-shopper validation on the way. The heavy simulation runs on PyTorch with AMD ROCm.

**Tags:** AMD ROCm, PyTorch, Python, retail, demand forecasting, AI agents, pricing, inventory, ASP.NET Core, Angular

## 5. Plan to Oct 18

| Date | What |
|---|---|
| Oct 10 to 11 | You: download one public dataset (Dunnhumby) and check the repo is public. Me: demand check on it, the clean demo database, rehearsal |
| Oct 12 to 13 | Kick-off; ask the Q&A questions (pre-existing work; whether a local PesoWeb demo with a video is acceptable as the "application") |
| **Oct 14** | **AMD session** (about 2 hours): GPU check, Quick Sim on ROCm, record numbers and screenshots, destroy the server |
| Oct 15 | Record the demo video from the real system; enable GitHub Pages; final README pass |
| Oct 16 | Slides, cover image, fill in the form |
| Oct 17 | Buffer; final push and tag |
| Oct 18 | Submit before 10:00 PM PHT, well ahead |

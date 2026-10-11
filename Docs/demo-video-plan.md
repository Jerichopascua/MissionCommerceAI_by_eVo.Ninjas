# Demo video plan: Track 3 "Reinvent Commerce" (AMD Developer Hackathon Act III)

Written 2026-10-11. The script is in `video/make_pitch.py` (each scene's `say=` is the narration). This file is the reasoning and the checklist.

## 1. What the video has to do

The judges score four things ([05-judging-and-prizes.md](../amd-hackathon-act3-requirements/05-judging-and-prizes.md)). The video is the first thing most of them see, so each must be visible in it.

| Judging criterion | What the video shows | Scene(s) |
|---|---|---|
| **Presentation** | A problem a 15-year-old understands in 20 seconds, then the product working, then the technical depth | hook, problem, idea |
| **Application of technology** | The AI's prediction is statistics, not a language model alone; where AMD runs in the product | predict, setup, **AMD** |
| **Business value** | A real merchant problem, a useful action, a measured effect, honest limits | find, decide, cashier, evidence |
| **Originality** | One loop nobody joins up: expiry detection to rush sale to the shop's own customers to the cashier | the whole demo |

The brief's own tests ([02-track3](../amd-hackathon-act3-requirements/02-track3-reinvent-commerce.md)): *a real customer or merchant problem, a useful commercial action, relevant recommendations or personalization, a measurable effect*; and *if you predict demand, explain how, and do not use a language model as the only method*. Each has a scene.

## 2. What winning demo videos have in common

From published hackathon judging and pitch guides (sources at the end), which agree on these points:

1. **Problem first, one concrete figure, in the first 20 to 30 seconds.** Not the team, not the stack.
2. **Show the working product early and for most of the time.** About two thirds of a 3-minute video is the live product. No code on screen, no half-built features.
3. **One core action followed all the way through**, with visible output that proves it works, not a feature list.
4. **Short.** Common caps are 2 to 3 minutes; some events cut off anything longer and judges may stop watching. This event has **no stated limit** (the requirements list "demo video length/format limits" as a question for the Oct 13 Q&A). So we make two cuts and submit the one the rules allow.
5. **Technology is explained in the context of the product**, not as a separate lecture, and the sponsor technology is visibly part of the working product.

## 3. The structure (full cut about 4 minutes, short cut about 3)

| # | Time | Scene | Audience | What is on screen | Cut |
|---|---|---|---|---|---|
| 1 | 0:00 | **Hook**: 36 packs, 8 sold, 28 in the bin | a 15-year-old | three big numbers | both |
| 2 | 0:18 | **The problem** (Reinvent Commerce): shops have the data, not the decisions | everyone | one card | both |
| 3 | 0:37 | **The idea** in four lines: watches, suggests, tells customers, a person decides | everyone | four steps | both |
| 4 | 0:54 | **Demo 1**: the AI finds stock that will expire unsold (real company data) | merchant | Intelligent Hub, Loss prevention | both |
| 5 | 1:10 | **Demo 2**: Rush sale, filled in from the AI; the owner decides | merchant | Put on sale, prefilled | both |
| 6 | 1:24 | Demo 3: the register and the customers know at once | merchant | Put on sale, message log | full |
| 7 | 1:31 | **Demo 4**: a first-time customer registers on her phone | shopper | phone: login, register | both |
| 8 | 1:45 | Demo 5: she sees the rush sale; installs the app | shopper | phone: sale, install | full |
| 9 | 1:53 | **Demo 6**: reserves; gets a reference and a QR code | shopper | phone: sale, basket, code | both |
| 10 | 2:02 | **Demo 7**: the cashier keys the reference; the order is in the sale | cashier | POS Online order | both |
| 11 | 2:15 | **How the AI predicts** (not a language model): rate of sale, price response, expiry order, safe discount | technical | four steps | both |
| 12 | 2:41 | What the AI does: six capabilities, one rule (people decide) | technical | four rows | full |
| 13 | 2:57 | **The effect and its limits** | judges | three figures | both |
| 14 | 3:23 | **Setup and environment**: what runs where | technical | four boxes | full |
| 15 | 3:42 | **AMD**: what runs on AMD, with measured numbers | judges | numbers, `rocm-smi` | both |
| 16 | 4:00 | Close | everyone | one card | both |

The 15-year-old explanation is scenes 1 to 3 and the plain wording of every demo scene. The technical explanation is scenes 11 to 15.

Build: `python video/make_pitch.py --cut full|short`. Output `video/MissionCommerce_Pitch_<cut>.mp4`.

## 4. What we can honestly say today, and what we cannot

| Claim | Status | Evidence |
|---|---|---|
| The product works end to end on a real multi-tenant POS/ERP | **True** | live checks: put on sale 10/10, customer app 18/18, insight 7/7, loss prevention and expiry risk |
| The prediction is not a language model | **True** | `ai/missionai/demand.py` (Poisson price-slope, maximum likelihood), `optimizer.py`, FEFO queue; an architecture test forbids the model in the decision path |
| A language model words notes and cannot invent a figure | **True, model path tested with a stand-in model** | `ai/missionai/insight.py`, 14 tests; not yet run against a real hosted model |
| AI shop ahead on 10 of 10 days, about +8% gross margin | **True, simulated shoppers, A/A checked** | `Docs/showcase-results.md` |
| Price awareness lowers forecast error 10 to 12% on real shoppers | **True**, but only about 1% better than the best simple baseline in the deployed form | `Docs/real-data-demand-check.md` |
| **A meaningful part of the workload runs on AMD** | **NOT YET DONE** | see section 5. The one `results/quicksim.json` in the repo is a CPU run |

**Do not use** the diagrams in `Graphics_Presentations/` as they are. They show the original plan ("What we will use": LightGBM, FastAPI, DuckDB, an AMD aggregated lane). Parts of that are not what was built, and the AMD parts are not done. Redraw them from what exists (scenes 11 and 14 already do).

**Do not claim** an AMD result until `results/amd-session.json` has `amd: true`. `make_pitch.py --final` refuses to build otherwise, and the AMD scene is drawn as a red DRAFT placeholder.

## 5. The AMD part: what to run and capture

The rule: *a meaningful part of the workload on AMD infrastructure, as part of the working product shown to judges.* Two things in the product genuinely use a GPU, and both are visible:

1. **The shopper simulation (Quick Sim)**: persistent shoppers as rows of a tensor on PyTorch/ROCm, 200,000 shoppers for 28 days. The same demand model and anomaly detector then run over the result. Shows scale and speed against the CPU.
2. **The language model that words AI Insight notes**: Qwen on vLLM (ROCm), reached through `LLM_BASE_URL`. In the product, the notes marked "AI wording" in the Hub come from it, and any note with an invented figure is refused.

**Capture session (about 2 hours, plan Oct 14, destroy the server afterwards):**

1. Follow **[amd-session-runbook.md](amd-session-runbook.md)** step by step (it covers the server, the container, the model, the collector and the recordings). The sections below are the summary.
2. Start the model server (Test 0 in the guide): `python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --host 127.0.0.1 --port 8000`.
3. Collect the evidence in one run:
   `python scripts/amd_session_collect.py --out ../results/amd-session.json --llm-base http://127.0.0.1:8000 --llm-model Qwen/Qwen2.5-7B-Instruct`
   It records the GPU, ROCm/HIP and PyTorch versions, `rocm-smi`, matrix-multiply TFLOPS, Quick Sim on GPU and on CPU (time and speed-up), and how many notes the model reworded and how many were refused.
4. **Screen-record** (this is the footage for the video): (a) a terminal with `rocm-smi` while the model answers; (b) the Quick Sim run on the GPU; (c) PesoWeb's Intelligent Hub pointed at the AMD endpoint (`LLM_BASE_URL`), pressing **Refresh the notes** and the notes marked "AI wording" appearing.
5. Rebuild: `python video/make_pitch.py --cut full --final` (refuses unless the run was real).
6. Put the numbers and one screenshot in `Docs/amd-smoke-test.md`, and the same in the project description.

If the whole stack cannot be moved to the AMD server, run only the GPU parts there and say so: *the shop system runs on one PC, the GPU workloads run on the AMD Developer Cloud*. That is still "a meaningful part of the workload", provided it is shown working, not described.

## 6. Production checklist

- [ ] AMD session done; `results/amd-session.json` has `amd: true`; AMD scene shows real numbers
- [ ] Voice-over by a person (the build uses Windows' built-in voice, which sounds robotic). Same script, record once, replace the `.wav` files
- [ ] Two cuts: 3-minute (short) and about 4 minutes (full); check the event's limit at the Oct 13 Q&A
- [ ] Captions burned in (many judges watch muted); the demo scenes already carry a caption bar
- [ ] Check every figure on screen against `Docs/` (section 4)
- [ ] The shop data in the demo is the real test company (520 Minimart); no real customers' data on screen
- [ ] Export 1080p; upload as unlisted; test the link while logged out
- [ ] Cover image (the key frame: the phone with the SALE banner next to the Hub)

## Sources (video advice)

- [Hackathon Demo and Presentation Tips: How to Pitch in 3 Minutes and Win](https://blogs.reskilll.com/hackathon-demo-presentation-tips-pitch-3-minutes-win-2026/)
- [The 3-Minute Pitch: How to Win a Hackathon](https://musichackspace.org/blog/hackathon-presentation-tips)
- [How to win Shipaton, part 4: pitching your app](https://www.revenuecat.com/blog/engineering/how-to-win-shipaton-part-4-pitching-your-app)
- [How to make your Devpost submission not suck](https://dev.to/jacklyn/how-to-make-your-devpost-submissions-not-suck-37i0)
- [Lessons from Winning Five Hackathons](https://sustained.substack.com/p/lessons-from-winning-five-hackathons)

These are practitioner guides, not a study: treat the timings as convention.

# Customer actors: people with their own situation, memory and judgement

Your chicken story, built and run against the local PesoWeb. This page says what the customers are, how they decide and learn, what the system sees, the real numbers, and what is still an assumption.

## 1. Your story, mapped to what the program does

| In your story | In the program |
|---|---|
| A man lost his job and is saving money | Marco: `budget_stress 0.9`, thrift 0.9, patience 0.8, sociable 0.8. Money is tight, so he cannot pay full price but will buy at half |
| He goes at 9 PM and finds cooked chicken at 50% off, and buys it | Day 1 and 2 had no clearance yet, so he found nothing he could afford. From day 3 the shop's AI cuts the price at 20:30 and he starts to learn about it (from a friend on day 3) |
| Next time he comes at 7 PM, price is normal, asks the cashier | Day 4: he arrives at 19:00, sees 250, asks, and the cashier answers from the shop's own record: "the price usually drops around 20:30" |
| He waits until the price is cut and buys 3 | "chicken is 250, too much; I will wait" ... "saw the price drop right when it happened at about 20:30" ... "bought 3 at 125 each (a bargain, so I took extra)" |
| He tells his friends | "told 4 friends about it". Friends in a similar situation get the tip with a weaker belief and adjust their own evenings |
| The system should notice the change in behavior | A detector on the AI side reads only purchase records and reports: "Customers now buy 0.9 h later (median 19:38 -> 20:30); clearance-priced units went from 0% to 85% of sales" |
| So the price cut is clearing stock instead of losing it | The same neighbourhood is run three ways and compared (section 4) |

## 2. What a customer is

Each of the 40 customers in the neighbourhood has:

- **Traits:** how tight money is, how hard they hunt for bargains, patience, sociability, how often they want chicken, and the hour they shop when they know nothing.
- **A belief:** "the price usually drops around HH:MM", and how sure they are of it. A customer who has never seen a cut has no belief and shops at their habit hour at full price. Nothing is told to them in advance.
- **Memory and a diary** in plain words (you can read a customer's whole life in the output).
- **Friends:** people in a similar situation.

Every evening they act in 15-minute steps between 17:00 and 22:00:

1. Decide whether they want chicken tonight, and when to arrive (habit hour, or a bit before the cut hour if they believe in it).
2. At the shop, look at the shelf price and the stock. If they can pay, they buy (a bargain makes a thrifty person take extra). If not, they **ask the cashier** if unsure, **wait** if the cut is close enough for their patience, or **leave**.
3. Learn: from seeing the price drop, from the cashier, from a friend, from missing out ("everything was gone; next time I come earlier"), and from a belief that fails ("the price did not drop when I expected; I trust my guess less now").
4. Tell friends after a bargain.

Some comfortable customers are bargain hunters too: they can afford full price but time their visit to the cut once they trust it. That is what lets the system lose some full-price sales when people learn to wait, instead of assuming it away.

## 3. How "judgement" works, honestly

**It is not an LLM and not a trained model.** It is a transparent rule-based decision model (what can I afford, what do I believe, how long will I wait) with small bounded noise. We chose that so every decision can be explained and tested (23 unit tests on these rules). It does produce human-like arcs, like Marco's, but it is our simulation of behavior, not measured human behavior.

`Customer.decide()` is the place where a language model can supply the judgement for a few "hero" customers. **That is now built as an option** (`sim/simpeso/llm_hero.py`, section 5 below); by default no shopper uses a language model. Customers with `adaptive=False` never learn; they stand for the older statistical shopper and let us measure what learning changes.

## 4. What the system saw, and the numbers

Setup: a shop sells 12 cooked whole chickens a day (cost 110, price 250, must go tonight). Days 0 to 2 have no clearance, so the AI learns the normal sales rate and hour pattern. From day 3 the markdown agent may cut prices from 20:30 inside the owner's rules (never below cost + 5%, at most 50% off). All stock, shelf prices, markdowns and prices paid come from the real PesoWeb. Same seeded neighbourhood three ways, 5 seeds, mean per evening over days 3 to 13 (`results/story.json`):

| | No clearance | Clearance, customers never change | Clearance, customers learn |
|---|---|---|---|
| Chickens thrown away (pesos) | 926 | 424 | **46** |
| Revenue (pesos) | 895 | 1,448 | 1,823 |
| Net after waste (pesos) | -425 | +128 | **+503** |
| Full-price units per evening | 3.6 | 3.4 | 3.0 |
| Clearance-priced units per evening | 0 | 4.7 | 8.6 |

What the behavior detector reported for the learning arm (per seed): in the seeds where customers visibly moved, "Customers now buy about 1.1 h later (median 19:38 -> 20:30)", clearance units from 0% to 68 to 88% of sales, and in some seeds full-price units fell (for example 3.7 to 1.4 per day). It also says "No reliable change" when the shift is not bigger than chance; it does not force a finding.

How to read it:

- The cut works as clearance: waste falls from about 926 to 46 pesos a night and net turns positive.
- **Learning customers change the picture.** The same clearance clears much more stock when customers learn the time and wait for it, because people who would otherwise have gone home buy at the cut. Part of that is a direct consequence of how we modelled the customers, so read the gap between the last two columns as "what happens if people behave like this", not as a measured fact about real shoppers.
- There is a cost: full-price units fall from 3.6 to 3.0 per evening because some bargain hunters now wait. The system sees it (the detector reports both numbers), which is exactly the trade-off an owner needs to weigh.

## 5. Problems we found by running it, and fixed

- **The first run of seed 2 never cut a price.** The AI's hour-of-day pattern comes from full-price sales, which show when people buy at full price, not when they would buy cheaper; so it believed nothing sells after 8:30 PM. We now mix a flat prior into the pattern (`prior_share`). This was changed after seeing that seed, which we want on record. The underlying lesson is real: sales at list price under-show demand that only appears at a lower price.
- The agent was also looking at old unsold lots (PesoWeb's clock does not move between our virtual days). It now acts only on tonight's lot.
- Customers who could afford full price bought it the moment they arrived even if they trusted a coming cut. A bargain-hunter rule fixed it, with a test.

## 6. Run it

PesoWeb must be running on port 5071 (see `concept-demo-guide.md`, Step 1).

    cd sim
    python -m simpeso.story --arm learning --days 12 --seed 3      # one run: day-by-day sales, Marco's diary, what the system saw
    python -m simpeso.story --compare --days 14 --seeds 1-5 --out ../results/story.json     # the three-way comparison (about 30 seconds)
    python -m unittest discover -s tests -t .                      # 105 tests (23 on customer behavior)

## 7. Limits to state out loud

- The customers' judgement is a rule-based assumption, not measured human behavior, and not an LLM.
- The evening clock (17:00 to 22:00) belongs to the simulator, because PesoWeb stamps sales with the server clock. Stock, prices, markdowns and prices paid are PesoWeb's own; the behavior detector reads purchase records (hour, price, quantity) kept by the simulator.
- One product, one shop, 40 customers, 14 evenings, 5 seeds. Word of mouth is a simple tip passed to friends.
- The shop's lot size (12) is large compared with full-price demand, so waste without clearance is high by construction.
- Mission detection (why a customer shops) is still not built.

## 5. Hero shoppers: a few shoppers whose judgement comes from an AI API (optional)

A hero shopper has a **persona** (who they are) and a **mission** (what they came for tonight). At each 15-minute step the language model chooses buy (how many), ask the cashier, wait or leave, in character. Their memory, belief and learning stay in the same `Customer` object, so the model is shown their diary and what they believe.

- **Which AI API:** any of these, picked from environment variables (the key is never written to a file or printed): `ANTHROPIC_API_KEY` (Anthropic Messages API; model `LLM_MODEL`, default `claude-haiku-4-5-20251001`); or `LLM_BASE_URL` + `LLM_MODEL` for any OpenAI-compatible server (vLLM on the AMD GPU, or a hosted one; `LLM_API_KEY` optional); or `OPENAI_API_KEY`.
- **What is sent:** only the synthetic persona and what a shopper could see (time, the shelf price and the usual price, stock left, their own belief and diary). Nothing from PesoWeb's data and nothing about the shop's AI.
- **Safety:** every answer is validated (a known action, a sensible quantity, within the stock, something the shopper could afford). Anything else, a network error or a spent budget falls back to the rule-based decision, so a bad call never stops a run. `--max-llm-calls` (default 300) is a hard cap on real calls. Answers are cached in `sim/runs/llm_cache.jsonl`, so repeating a run replays it identically and costs nothing.
- **Personas:** four are built in. For more variety use a JSONL file of synthetic personas, for example a sample of NVIDIA's Nemotron-Personas (`--personas file.jsonl`; each line `persona` or `occupation`/`age`/`city`, and optionally `mission`).
- **Try it without a key:** `python -m simpeso.story --arm learning --days 6 --seed 3 --heroes 4 --llm stub` runs the whole flow against PesoWeb with an offline stand-in that behaves plausibly.
- **With a real API:** set the key in the same window, then `python -m simpeso.story --arm learning --days 6 --seed 3 --heroes 4`. Start with a small number of heroes and days; each decision is one short call.
- **Honest limit:** a model playing a person is still a simulation. It adds human-like variety, but it carries the model's own biases and is not measured behaviour. It is validated, as everything else here is, only against real sales data.

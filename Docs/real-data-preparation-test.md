# Pre-data preparation test: real catalog with perishable products

Recorded 2026-10-05, before the showcase run. No real product names or prices appear here; those stay in the git-ignored `sim/runs/` folder.

## What was prepared

| Step | Result |
|---|---|
| Backup first | both dev databases backed up and verified, git tag `pre-showcase`, private files zipped (`C:\Users\Lito\PesoWeb_Backups`) |
| Real catalog | 493 real products (real cost and price) extracted from the restored v2 copy, test rows dropped |
| Perishables | 21 products (4.3%) matched by explicit name rules in `sim/simpeso/perishables.py`, in 7 classes (chilled dairy 7 to 21 days, chilled meat 14 to 45, prepared salad 3 to 7, chilled side dishes, chilled spreads and cheese, packaged cakes, soy milk). Review list: `sim/scripts/check_perishables.py` (writes `sim/runs/perishables_review.txt`). 40 other products looked perishable by a broad keyword and were deliberately excluded (instant noodles with "cheese", detergent with "fresh", canned corned beef, wafers, bread crumbs...) |
| Worlds | `real2` (agent on) and `real3` (agent off): 5 companies, 10 branches, every branch sells all 493 products, 21 of them expiry-tracked with 4 batches each |

## Pre-data checks (all passed)

- Every tenant: 493 products, 21 expiry-tracked and batch-tracked, 84 stocked batches, all with expiry dates.
- Costs and prices in PesoWeb match the real catalog exactly (0 mismatches among the perishables, 0 among 493 products in a full check).
- A simulated day on the real catalog ran with no failed sales.

## First trial on real perishables (one seed, agent on vs off, identical worlds)

| | Agent off | Agent on |
|---|---|---|
| Short-dated lots in the trial | 53 | 53 |
| Waste at the end (pesos) | 9,820 | 9,560 (-2.6%) |
| Units sold | 175 | 183 |
| Revenue (pesos) | 10,648 | 10,766 (+1.1%) |
| Markdowns applied / refused | 0 | 12 / 0 |

Prediction quality for the 12 markdowns: units error 1.56 against 1.25 for a naive guess (worse than naive), 50% of outcomes inside the 80% interval, predicted waste 556 against 706 realized.

## What this tells us

- **On real prices the AI has little room.** Chilled dairy carries 27 to 36% margin over cost and gets markdowns. Processed meats, spreads, cakes and kimchi carry about 2 to 13%, so with a floor of cost + 5% almost every discount step is blocked and the agent correctly does nothing. Most of the waste sits in those thin-margin lots, where no markdown is safe. This is the honest limit of "agentic markdown" on a thin-margin mini-mart, and a good thing to say on stage.
- **The agent's predictions are not reliable at this scale** (lots of 4 to 5 units, one seed). The earlier five-seed proof on generated catalogs is the better evidence for the mechanism.
- Only chilled dairy sold often enough to learn a price slope (-2.56); the other classes stay at the starting guess.

## Assumptions to keep in view

- Shelf lives and the choice of perishables are rule-based guesses; the source data has no expiry information. Processed meats are often sold frozen, so 14 to 45 days is conservative.
- Chilled staples have a popularity floor (they sell daily in a real store even though the small real sample saw few sales).
- One seed, 10 branches, 6 history days.

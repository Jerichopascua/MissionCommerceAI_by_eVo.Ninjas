# PesoProfit showcase on the real catalog: what happened, and what it means

Recorded 2026-10-06. Real Alma Store catalog (493 products with real cost and price; 21 given short expiry dates), 5 companies with 2 branches each. The same shop twice: `real3` has no AI, `real2` has the AI Pricing flow and the markdown agent. Margin floors 5% hard / 10% soft. Product names and prices are the store's public shelf data.

## Short answer

With a fair comparison, the AI made the shop a little more profitable on **every one of 10 trial days**: gross margin about +8% (roughly +220 to +250 pesos a day on about 2,500 to 3,500), revenue and units about flat. The markdown agent added a small further gain by cutting waste about 160 pesos a day. The effect is modest, it comes mostly from fixing prices that sat below the margin floor, and shopper reaction is the simulator's own assumption.

## A correction you should know about

My first two comparisons (trial days 201 to 213) said the AI lost on every day. They were wrong. The two worlds were not true twins: real2 had lived through many more simulated days and had sold down its shelves, so with no AI and no price change it still sold about 22% fewer units than real3. I found this with an **A/A check** (the same day in both worlds, no AI, no price change) and fixed it by giving both worlds the same shelf stock, the same short-dated lot sizes, and no leftover lots from earlier trial days. After that the A/A check shows **exactly zero difference over five days**, and everything below is measured that way. The earlier numbers are discarded.

## 1. The flow works end to end

1. AI Pricing was requested through the AI Control API and run by the agent runner. It browsed all 493 products with their cost.
2. It put **301 proposals** in the Approval Center: 165 margin fixes (products priced below cost plus 5%, raised to that price) and 136 profit-based changes (at most 15 per company, from the price advisor).
3. The simulated approver approved 157, approved half the step on 42 and rejected 102; 0 failed. 199 list prices changed in PesoWeb (mean +2.9%, largest +5.5%; average margin on those products from 4.6% to 7.2%). Only 13 were perishables.
4. A trial day followed: short-dated lots arrived and the markdown agent worked the day.

## 2. First day (day 225)

| | No AI | With AI | Difference |
|---|---|---|---|
| Revenue | 23,872 | 24,473 | +601 |
| Gross margin | 2,748 | 2,989 | +241 |
| Waste (pesos) | 7,566 | 7,692 | +126 |
| Net (margin minus waste) | -4,818 | -4,703 | +115 |
| Units sold | 399 | 416 | +17 |

## 3. Ten more days, separating the two effects

Same shoppers, same stock and same lots in both worlds each day. The AI world kept the approved new prices; the markdown agent was ON for days 226 to 230 and OFF for days 231 to 235. Mean difference to the no-AI world on the same day, pesos per trial day (waste: negative is better):

| AI world setting | Revenue | Gross margin | Waste | Net |
|---|---|---|---|---|
| New prices, markdown agent ON (5 days) | -55 | +223 | -86 | +309 (5 of 5 days better) |
| New prices, markdown agent OFF (5 days) | +40 | +249 | +76 | +173 (5 of 5 days better) |

What the markdown agent adds on top of the new prices: revenue -95, margin -25, waste -162, net +136 per day.

| Day | Markdown agent | No-AI net | AI net | Difference |
|---|---|---|---|---|
| 226 | on | -5,381 | -5,201 | +180 |
| 227 | on | -6,130 | -5,790 | +339 |
| 228 | on | -7,062 | -6,636 | +425 |
| 229 | on | -3,081 | -2,988 | +93 |
| 230 | on | -4,713 | -4,206 | +508 |
| 231 | off | -3,759 | -3,524 | +235 |
| 232 | off | -5,721 | -5,697 | +24 |
| 233 | off | -4,322 | -4,210 | +112 |
| 234 | off | -7,050 | -6,780 | +270 |
| 235 | off | -6,943 | -6,722 | +221 |

## 4. How to read it

- **The gain is small and steady, not dramatic.** Net is margin minus the cost of unsold short-dated stock, which is negative here because the trial lots are deliberately over-sized so that markdowns have something to do. What matters is the difference, positive on all 10 days.
- **Most of it is margin fixing, not clearance.** The price changes added about +8% gross margin with units about flat. The markdown agent then trimmed waste by about 160 pesos a day (about 2%) and added about +136 net; it applied only the smallest 10% step, because margins are thin.
- **What the simulator assumes:** shoppers' price response is the simulator's own hidden elasticity (about 0.7 to 2.8 depending on shopper type); the AI never sees it. A real shop may react differently, which is why a price test should come before broad raises.
- **Still true:** the two markdown settings ran on different days, so their difference is an estimate; one trial day is not a month of trading; there is no competitor price feed; the approver's waiting time is not simulated; a real owner would review proposals, not approve 157 at once.

## 5. What to show

- **Headline:** the generated-shop proof (markdown agent -58% waste against doing nothing over 5 seeds, tied with a fixed 30%-off rule), and the real-catalog run as the proof the whole loop works on real prices: AI proposes, rules check, a person approves, PesoWeb applies, margin rises on every trial day.
- **Be plain about the size:** on real thin margins the benefit is a few percent of gross margin, not a transformation.

## 6. The 15 largest list-price changes in the AI world

| Company | Product | From | To | Change | Margin before | Margin after |
|---|---|---|---|---|---|---|
| c3 | RED HORSE BEER CAN 330ML | 55 | 58 | +5.5% | 9.1% | 13.8% |
| c3 | REBISCO HANSEL CHOCO 10S(31G) | 65 | 68.5 | +5.4% | 13.1% | 17.5% |
| c1 | SANMIG COFFEE STRONG SFREE 9G | 85 | 89.5 | +5.3% | 8.2% | 12.8% |
| c1 | PRIDE PWD W.MACHINE 1KG | 95 | 100 | +5.3% | 7.4% | 12.0% |
| c1 | PRIDE DET PWD KALAMANSI 1000G | 95 | 100 | +5.3% | 5.3% | 10.0% |
| c1 | RED HORSE BEER LITRO | 125 | 131.5 | +5.2% | 20.0% | 24.0% |
| c1 | PUREFOODS LMEAT CHINESE 350G | 87 | 91.5 | +5.2% | 5.7% | 10.4% |
| c2 | VIDA BACON 250G | 105 | 110.5 | +5.2% | 9.5% | 14.0% |
| c3 | RENO LIVER SPREAD 230G | 58 | 61 | +5.2% | 8.6% | 13.1% |
| c4 | REBISCO DOOWEE DONUT STRAWBERRY 420G | 105 | 110.5 | +5.2% | 6.7% | 11.3% |
| c3 | REBISCO COMBI TRPLE CHOC(B)10S(30G) | 68 | 71.5 | +5.1% | 13.2% | 17.5% |
| c4 | SURF FBCN LUXE PRFM R BOT 800ML | 137 | 144 | +5.1% | 7.3% | 11.8% |
| c4 | PRIDE PWD FBCN SAKURA 1KG | 99 | 104 | +5.1% | 8.1% | 12.5% |
| c1 | SSK SHMP SMTH&MNGABLE P 2/180ML-P | 210 | 220.5 | +5.0% | 9.5% | 13.8% |
| c1 | SSK SHMP STRNG&LNG G 2/180ML-P | 210 | 220.5 | +5.0% | 9.5% | 13.8% |

## How this was produced

`sim/scripts/aa_check.py` (twins check, zero difference), `showcase_preflight.py`, `showcase.py` (flow and day 225), `showcase_days.py` (days 226 to 235), with `sim/simpeso/equalize.py` equalising stock and lots before each day (it clears leftover trial lots directly in the throwaway test database, as test-bench housekeeping). The database was backed up and restored between runs. Raw outputs are in git-ignored `sim/runs/showcase*.json`; the discarded biased runs are kept there as `biased-unequal-worlds-*`.

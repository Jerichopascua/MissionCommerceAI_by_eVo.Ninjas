# PesoProfit showcase on the real catalog: what happened, and what it means

Recorded 2026-10-06. Real Alma Store catalog (493 products with real cost and price, 21 given short expiry dates), 5 companies with 2 branches each. The same shop twice: `real3` has no AI, `real2` has the AI Pricing flow and the markdown agent. Margin floors 5% hard / 10% soft. Product names and prices are the store's public shelf data.

## Short answer

On this thin-margin catalog the AI did **not** make the shop more profitable in the simulation. Raising prices cost sales, and the markdown agent had little room to help. The numbers below are exactly as run, including the bad ones. The earlier proof on generated shops with normal margins (waste down about 58% over 5 seeds) is a separate result and still stands; it does not carry over to your real prices.

## 1. The flow works end to end

1. AI Pricing was requested through the AI Control screen's API and run by the agent runner. It browsed all 493 products with their cost.
2. It put **301 proposals** in the Approval Center: 165 margin fixes (products priced below cost plus 5%, raised to that price) and 136 profit-based changes (at most 15 per company, from the price advisor).
3. The simulated approver approved 157, approved half the step on 42 and rejected 102. 0 failed. 199 list prices changed in PesoWeb (mean +2.9%, largest +5.5%; average margin on those products from 4.6% to 7.2%). Only 13 were perishables, so most of the margin room was created on ordinary products.
4. A trial day followed: short-dated lots arrived and the markdown agent worked the day (48 markdowns applied, none refused by the rules).

## 2. The first day (day 203)

| | No AI | With AI | Difference |
|---|---|---|---|
| Revenue | 20,871 | 16,068 | -4,803 |
| Gross margin | 2,367 | 1,909 | -457 |
| Waste (pesos) | 10,525 | 9,474 | -1,051 |
| Net (margin minus waste) | -8,158 | -7,565 | +594 |
| Units sold | 361 | 282 | -79 |

Waste fell about 10% and net was +594, but revenue and gross margin fell. One day is noise, so I ran more.

## 3. Ten more days, separating the two effects

Same shoppers and lots in both worlds each day. The AI world kept the approved new prices; the markdown agent was ON for days 204-208 and OFF for days 209-213. Mean difference to the no-AI world on the same day, pesos per trial day (waste: negative is better):

| AI world setting | Revenue | Gross margin | Waste | Net |
|---|---|---|---|---|
| New prices, markdown agent ON (5 days) | -6,877 | -649 | +678 | -1,327 (0 of 5 days better) |
| New prices, markdown agent OFF (5 days) | -2,793 | -147 | +399 | -546 (0 of 5 days better) |

What the markdown agent adds on top of the new prices: revenue -4,084, margin -502, waste +279, net -781 per day. The AI world was behind the no-AI world on every one of the 10 days.

## 4. Why (what I can see, and what I cannot)

- **The raises cost volume.** Shoppers in the simulator respond to price with a hidden assumption the AI never sees. At about +3% on 199 products, revenue fell 3-7k pesos a day and margin did not make it back. That is the simulator's assumption, not a measurement of your customers; it is also exactly why a price test should come before a broad raise.
- **The markdown agent had little to work with.** It applied only the smallest step (10% off) on 3 to 12 batches a day. On thin margins a 10% cut on stock that would mostly sell anyway gives margin away. Its expectation rests on an assumed price sensitivity, and in this world the shoppers disagree.
- **The approver approved a lot at once.** A real owner would not approve 157 raises without testing. The price test (switchback and group designs) exists for this and was not used in this run.
- **Not separated or not modelled:** the two settings ran on different days, so their difference is an estimate; waste in both worlds drifts up over repeated trial days (probably stock carrying over, not checked), which affects both worlds alike; no competitor prices; the approver's waiting time is not simulated.

## 5. What I would show, and what to do next

- **Headline the generated-shop proof** (margins normal): markdown agent -58% waste against doing nothing over 5 seeds, tied with a fixed 30%-off rule. State plainly that on your real thin margins it does not pay.
- **Show the real-catalog run as the honest limit and the guardrail story:** the AI proposed 301 changes, every one went through the rules and a person, and the system never let a price go below cost plus the floor. That is the value of the Approval Center.
- **Next experiment worth running:** gate raises behind the price test (raise a small group first, learn the real response, then propose), and let the markdown agent skip products where its expected gain is small. Both are changes in `ai/missionai`, not in PesoWeb.

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

`sim/scripts/showcase_preflight.py` (checks prices and policy), `sim/scripts/showcase.py` (flow and trial day 203), `sim/scripts/showcase_days.py` (days 204-213). The database was backed up before and restored between dry runs (two earlier dry runs had a flaw in the simulated approver, since fixed; their output is not used). Raw outputs are in git-ignored `sim/runs/showcase*.json`.

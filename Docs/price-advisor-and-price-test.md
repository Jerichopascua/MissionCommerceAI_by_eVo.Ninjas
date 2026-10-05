# Price advisor and price test

Recorded 2026-10-05. No real product names or prices appear here (they stay in the git-ignored `sim/runs/`).

## 1. The price advisor (`ai/missionai/price_advisor.py`, `sim/scripts/price_advice.py`)

The agent browses every product of a company through PesoWeb's own product list (cost, price, stock) and suggests a selling price that maximises profit per day, `(price - cost) x units`, with units following `units_now x (price / price_now) ^ beta`.

Limits on every suggestion: a bounded step (default 10%) from today's price; never below the **margin price** (cost + the owner's hard floor); a **no-regret check** (it must still not lose if customers are one step more price-sensitive than assumed); no demand-based suggestion for a product with no sales evidence. For every product it also reports the margin price, the soft price and the room to lower the price, which is the floor the markdown agent uses for clearance. It only suggests; nothing is changed in PesoWeb.

First run on the real catalog (one company, 493 products): 56 raises of about 10%, 4 holds, 433 with no sales evidence. Expected gain about 300 pesos a day (conservative 231) against about 470 a day of current profit on the products with evidence. **At first 55 of the 56 rested on an assumed sensitivity**, and there is no competitor price feed, so thin-margin staples priced to match a rival need an owner check. They are hypotheses to test.

## 2. The price test (`ai/missionai/price_test.py`, `sim/simpeso/pricetest.py`)

A list price belongs to the whole company in PesoWeb, so a test cannot raise a price at one branch only. Two designs were built and tried on the real-catalog world (48 best-selling non-perishable products, +20%):

| Design | Estimated sensitivity | 95% interval | Reliable | True response (hidden from the AI) |
|---|---|---|---|---|
| Two groups: 2 companies raise, 3 stay (first run, 24 products, +10%) | -3.9 | -8.3 to +0.5 | no | -1.24 |
| Two groups (48 products, +20%, 10 test days) | -0.12 | -1.90 to +1.66 | no | -1.28 |
| **Switchback: all 5 companies alternate raised and normal days (16 days, balanced random pairs)** | **-1.38** | **-2.23 to -0.53** | **yes** | **-1.32** |

The switchback design needs far fewer units for the same precision because every shop is its own control. Its estimate recovers the simulator's true response and the model moves from its assumed -1.30 to a measured -1.37. Afterwards 51 of the 56 suggestions rest on a learned sensitivity instead of 1. The advice itself did not change, because the measurement confirmed the assumption (with a stated error bar) rather than overturning it. Test prices were restored afterwards (0 products differ from the real catalog).

## 3. A bug this exposed, and the fix

The first run fed 24 noisy product observations into the model as if each were an independent sale. A weak test then **dragged the model from -1.30 to -2.86**, away from the truth. Test results now enter as one estimate weighted by its precision (inverse variance, with the starting guess counting as one piece of evidence with a standard error of 1.0), so a noisy test barely moves the model and a precise one dominates. Covered by tests; the polluted observations were removed from the saved model.

## 4. Limits

- The "true response" is the simulator's own hidden shopper behavior. The test shows it can recover an effect of that kind; it says nothing about real customers.
- A real price test costs money while it runs (customers lost on raised days); this was not measured here.
- Evidence is for the pooled grocery category, from 48 products; it does not give per-product sensitivities. Perishables keep their own learned slopes from the promo days.
- There is still no competitor price feed, and raises are only suggested. Applying a list-price change with a guarded, logged approval step in PesoWeb has not been built.

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
- There is still no competitor price feed, and raises are only suggested. 

## 5. Approve and apply (built, PesoWeb change)

PesoWeb now has a guarded approval step for **list-price changes** (company-wide), separate from per-batch markdowns:

| Endpoint | Who | What |
|---|---|---|
| `POST /api/Pricing/ListPrice` | the AI or a person (permission `Pricing.Markdown`) | propose a new list price; rules are checked; a safe proposal waits for approval (202), an unsafe one is refused and recorded (422) |
| `POST /api/Pricing/ApproveListPrice` | a person (`Pricing.Approve`) | re-checks the rules against today's cost and price, then applies the price, writes the ledger row and publishes a `PriceChanged` event |
| `POST /api/Pricing/RejectListPrice` | a person (`Pricing.Approve`) | closes it; nothing changes |
| `GET /api/Pricing/ListPriceChanges` | `Pricing.View` | the ledger of list-price changes |

Rules (`Services/ListPriceGuardrails.cs`): a list-price change **always needs a human approval**, whatever the autonomy mode; never below cost + the hard floor (on the net price after the product discount); a decrease no deeper than the maximum discount; an increase of at most 15% in one step; no more than the policy's changes per product per hour; refused while the product has an active markdown; refused if the list price moved or the cost changed since the proposal; autonomy Off or no policy refuses everything. Hard limits cannot be waived by approving. The 15% increase cap is a constant in code, not yet a policy setting.

Live check against the real-catalog world (`sim/scripts/apply_price_advice.py`): the AI proposed 6 changes (all wait, no price moves), a +40% jump and a below-cost price were refused with reasons, the owner approved 3 (prices changed in PesoWeb and a real sale was charged the new price), rejected 1 and left 2 pending, and the ledger held every attempt: **22 of 22 checks passed**. Afterwards the three prices were restored through the same approval step and the pending ones closed (0 products differ from the real catalog). PesoWeb unit tests: 144 pass (25 new).


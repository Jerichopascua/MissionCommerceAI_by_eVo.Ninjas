# Demand model against real shoppers: Dunnhumby "The Complete Journey"

Run on 2026-10-10 with `python -m simpeso.validate demand --datasets dunnhumby`. Numbers: `results/validation-demand-dunnhumby.json`.

## What was tested

The price-aware demand model our AI uses (`ai/missionai/demand.py`: units in a window follow a Poisson law whose mean is a base rate times (price / usual price) to the power of a price slope, fitted by maximum likelihood) was fitted on real supermarket sales and asked to predict days it had not seen.

- **Data:** about two years of purchases by 2,500 households at a US supermarket chain (2.6 million till lines). Price paid = sales value divided by quantity, per product per day. A US data set, so it tests the method, not Philippine shoppers.
- **Products:** the 150 best-selling ordinary products that sold on at least 200 days. Lines with more than 20 units (weighed or bulk lines) were left out.
- **Split:** for each product, the first 70% of its days to fit, the last 30% to predict: 31,744 product-days, of which 19,546 had a price at least 5% away from usual.
- **Measure:** WAPE, total absolute error over total units (lower is better).
- **Compared against:** the all-history average, the average of the last 28 days, and "the same weekday last week". None of them looks at price.

## Result

The price slope the data gave is **−1.29** (73,791 fitted points). It comes out the same whatever starting guess the model is given, and it is in the range usually seen for groceries: a 10% higher price sells about 12% fewer units.

| WAPE on the 19,546 days when the price moved | Without price | With price | Error lower with price |
|---|---|---|---|
| Fixed level (all-history average as the base rate) | 0.630 | **0.569** | **9.7%** |
| Recent level (last 28 days as the base rate, as the AI uses it) | 0.709 | **0.623** | **12.2%** |
| Same weekday last week (no price) | 0.885 | | |

**Honest reading.**
- Level for level, adding price awareness lowers the error by about **10 to 12%** on real shoppers.
- Against the best simple baseline (the long-run average, 0.630), the form the AI actually uses (recent level, 0.623) is only about **1% better**, which the report calls "not clearly". The recent average is a noisy base for a single product at this volume.
- The error is high in absolute terms (about 57 to 62%) because a single product sells few units a day to 2,500 households, so day-to-day luck dominates. The data is a hard test for any daily forecast.
- Price awareness helps most where prices actually move, which is the case for markdowns and list-price changes.

## What changed between the first run and this one

The first run, on the 150 products with the largest raw quantity, was flawed: the list was dominated by weighed or bulk lines with enormous quantities and an average price of a fraction of a cent, and the fitted slope hit its upper limit (+0.5). On that run the price-aware model did **not** beat the baselines (WAPE 0.337 against 0.279 for the recent average). I fixed the product selection (ordinary shelf items only) and added the recent-level form of the model, which is how the AI uses it, then reported both forms. The first result is kept in `sim/runs/validation-demand-first-run.json` (git-ignored). Both setups were chosen for being sensible, not for the answer; the selection rule was fixed before the second run.

## What this does not show

- It does not show that the AI raises profit in a real store; that needs the control-branch comparison in the Hub with real sales.
- It uses US sales, daily totals over all stores, and a single price per day (a day with both full and promotional prices is averaged).
- Our model has one slope for the whole data set here; per-category slopes would need category labels, which the transaction file does not carry.

# Primary statistics on development data (method v2)

Development data only (bars before the hold-out start). Exploratory: this is where the claims come from, so these numbers cannot confirm anything.

Cells: estimate [95% confidence interval] and one-sided p-value in the claimed direction (studentised joint-date block bootstrap, t reference, inflation factor from the calibration study).

## A. Stocks: relative timing (own-history percentile x return rank across stocks)

| Claim | 1d | 3d | 7d | 14d | 30d |
| --- | --- | --- | --- | --- | --- |
| A1 Stretch (+) | -0.004 [-0.015, +0.007] p=0.7536 | +0.000 [-0.018, +0.019] p=0.4854 | -0.003 [-0.028, +0.022] p=0.5890 | -0.003 [-0.032, +0.025] p=0.5878, p vs minimum=0.945 | -0.003 [-0.044, +0.038] p=0.5572 |
| A2 Trend (-) | +0.004 [-0.007, +0.015] p=0.7437 | +0.001 [-0.017, +0.019] p=0.5373 | +0.004 [-0.021, +0.029] p=0.6358 | +0.004 [-0.029, +0.037] p=0.5930, p vs minimum=0.923 | +0.003 [-0.045, +0.050] p=0.5463 |

First-run statistic at 14 days, in the claimed direction, next to the value it is expected to show with NO real effect (rotation null on the same data):

- A1: first-run statistic +0.045; expected with no effect +0.008
- A2: first-run statistic +0.058; expected with no effect +0.011

## B. Crypto: Trend ranking, top third minus bottom third (%)

| Horizon | Spread |
| --- | --- |
| 1d | +0.13 [+0.03, +0.24] p=0.0079 |
| 3d | +0.40 [+0.11, +0.69] p=0.0037 |
| 7d | +0.88 [+0.26, +1.51] p=0.0028 |
| 14d | +1.50 [+0.32, +2.67] p=0.0066, p vs minimum=0.048 |
| 30d | +2.44 [+0.11, +4.77] p=0.0201 |

At 14 days the spread splits into top third minus all coins +0.70% and all coins minus bottom third +0.80%.

Long-only top third against all coins equally weighted (same schedule and costs), 14 staggered tranches as one portfolio:

- base 0.20%: excess +11.2% a year [-3.7, +26.4]; top third +57.3% a year (max drawdown -92%), all coins +45.0% (max drawdown -92%); traded per rebalance 0.94 vs 0.09
- stress 0.50%: excess +4.9% a year [-10.2, +20.3]; top third +46.7% a year (max drawdown -92%), all coins +44.0% (max drawdown -92%); traded per rebalance 0.94 vs 0.09
- bitcoin buy and hold pct a year: +78.8

## C. ATR%: gain in rank correlation with later move size over each benchmark

| Claim | Benchmark | Gain |
| --- | --- | --- |
| C1 stock | trailing 14-day (primary) | +0.069 [+0.042, +0.096] p=0.0000, p vs minimum=0.000 |
| C1 stock | EWMA 0.94 | +0.064 [+0.044, +0.085] p=0.0000 |
| C1 stock | trailing 60-day | +0.080 [+0.033, +0.126] p=0.0005 |
| C2 crypto | trailing 14-day (primary) | +0.011 [-0.025, +0.046] p=0.2783, p vs minimum=0.699 |
| C2 crypto | EWMA 0.94 | -0.002 [-0.032, +0.028] p=0.5456 |
| C2 crypto | trailing 60-day | +0.044 [-0.006, +0.095] p=0.0413 |

Expected-move multipliers k (move within k x ATR% x sqrt(7) for 50% / 80% of asset-days):

- C1 stock: fitted 2016-2021 k50=0.446, k80=0.899; coverage 2022 to boundary 47.8% / 79.3%; fitted on all development k50=0.455, k80=0.906
- C2 crypto: fitted 2016-2021 k50=0.393, k80=0.869; coverage 2022 to boundary 50.6% / 80.5%; fitted on all development k50=0.390, k80=0.863

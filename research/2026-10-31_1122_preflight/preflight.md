# Preflight (development data only)

Spec hash 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61.

## Reproduction of the frozen v2 development estimates

- B: recomputed 1.4972999540605965, frozen 1.4972999540605965, match True
- C1: recomputed 0.06925556922726794, frozen 0.06925556922726794, match True
- C2: recomputed 0.010590860392287885, frozen 0.010590860392287885, match True
- all match: True

## Parity (development dates)

- 90 bars: largest difference 4.00 over 44 days
- 200 bars: largest difference 0.00 over 48 days
- 365 bars: largest difference 0.00 over 48 days

# Crypto Trend ranking: concentration diagnostic (development data only)

Descriptive robustness check of claim B (14-day top third minus bottom third, %). 95% intervals, no p-values. It does not change the primary test.

All coins: +1.50% [+0.32, +2.67], 2332 dates

## By calendar year

| Year | Coins with data | Spread |
| --- | --- | --- |
| 2016 | 0 | too few (0 dates) |
| 2017 | 1 | too few (0 dates) |
| 2018 | 17 | +0.52% [-3.92, +4.95], 218 dates |
| 2019 | 19 | +2.16% [-0.08, +4.40], 365 dates |
| 2020 | 21 | +3.46% [-1.46, +8.38], 366 dates |
| 2021 | 23 | +3.06% [-0.82, +6.94], 365 dates |
| 2022 | 23 | -1.17% [-3.25, +0.91], 365 dates |
| 2023 | 23 | +1.81% [-0.47, +4.09], 365 dates |
| 2024 | 23 | -0.08% [-1.85, +1.68], 288 dates |

## By Bitcoin regime and by half

- above 200-day: +2.59% [+0.83, +4.34], 1239 dates
- below 200-day: +0.26% [-1.16, +1.68], 1093 dates
- first half: +2.30% [+0.21, +4.39], 1166 dates
- second half: +0.69% [-0.57, +1.95], 1166 dates

## By coin

Contribution = the coin's average share of the daily spread (sums to the total). Leave-one-out = the spread with that coin removed from the universe.

| Coin | Contribution (%) | Days in top third | Days in bottom third | Spread without it |
| --- | --- | --- | --- | --- |
| ETC-USD | +0.401 | 26% | 35% | +1.38% |
| ADA-USD | +0.390 | 26% | 34% | +1.31% |
| BNB-USD | +0.378 | 49% | 17% | +1.27% |
| SOL-USD | +0.359 | 33% | 12% | +1.29% |
| ATOM-USD | +0.217 | 25% | 28% | +1.42% |
| TRX-USD | +0.182 | 42% | 22% | +1.46% |
| LINK-USD | +0.089 | 40% | 25% | +1.44% |
| BCH-USD | +0.064 | 25% | 35% | +1.34% |
| VET-USD | +0.061 | 28% | 22% | +1.49% |
| AVAX-USD | +0.054 | 20% | 14% | +1.49% |
| LTC-USD | +0.044 | 26% | 34% | +1.38% |
| DOT-USD | +0.025 | 13% | 16% | +1.49% |
| XTZ-USD | +0.018 | 30% | 33% | +1.60% |
| XLM-USD | -0.003 | 22% | 40% | +1.35% |
| XMR-USD | -0.032 | 41% | 22% | +1.72% |
| FIL-USD | -0.035 | 28% | 34% | +1.40% |
| NEO-USD | -0.035 | 29% | 25% | +1.52% |
| XRP-USD | -0.046 | 27% | 39% | +1.51% |
| DASH-USD | -0.050 | 21% | 36% | +1.70% |
| ZEC-USD | -0.098 | 27% | 34% | +1.45% |
| ALGO-USD | -0.122 | 21% | 28% | +1.54% |
| EOS-USD | -0.132 | 20% | 33% | +1.52% |
| DOGE-USD | -0.232 | 30% | 34% | +1.77% |

Without the three largest contributors (ETC-USD, ADA-USD, BNB-USD): +0.97% [-0.32, +2.25], 2332 dates

# DRY RUN on a pseudo window inside development (2022-10-30 to the boundary)

Spec hash 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61 (tag holdout-spec-v1).
Window from 2022-10-30; first eligible signals: stocks 2022-12-13, crypto 2022-11-29; prices up to 2024-10-29.

## Primary tests (Holm across all three)

| Test | Estimate [95% CI] | One-sided 95% bound | p | p vs minimum | Holm | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| B | +0.9159 [-0.4943, +2.3260] | -0.2531 | 0.09633 | 0.2742 | fail | Inconclusive |
| C1 | +0.0729 [+0.0260, +0.1197] | +0.0341 | 0.00190 | 0.0143 | pass | Confirmed, clearly above the minimum |
| C2 | +0.0031 [-0.0698, +0.0760] | -0.0576 | 0.46575 | 0.6795 | fail | Inconclusive |

## Exploratory: long-only crypto (not a test; ranking significance is not investable proof)

- base 0.20%: top third +31.9% a year (max drawdown -46%, one-way turnover 12.9x a year); equal weight +24.5% (max drawdown -46%); excess +6.6% [-15.1, +28.6]
  - against Bitcoin bought and held: +111.6% a year (max drawdown -26%); excess -42.0% [-87.0, +5.8]
- stress 0.50%: top third +22.0% a year (max drawdown -48%, one-way turnover 12.9x a year); equal weight +23.9% (max drawdown -46%); excess -0.7% [-22.7, +21.2]
  - against Bitcoin bought and held: +111.6% a year (max drawdown -26%); excess -49.8% [-94.8, -1.8]

## Exploratory: expected-move calibration with the frozen k (target 50% / 80%, tolerance 5 points)

- stock: 49.2% / 79.5%
- crypto: 49.0% / 79.5%

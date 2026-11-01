# HOLD-OUT evaluation (single run)

Spec hash 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61 (tag holdout-spec-v1).
Window from 2024-10-30; first eligible signals: stocks 2024-12-12, crypto 2024-11-29; prices up to 2026-10-30.

## Primary tests (Holm across all three)

| Test | Estimate [95% CI] | One-sided 95% bound | p | p vs minimum | Holm | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| B | +1.4649 [-1.1947, +4.1245] | -0.7398 | 0.13342 | 0.2306 | fail | Inconclusive |
| C1 | +0.0640 [+0.0104, +0.1177] | +0.0196 | 0.01066 | 0.0514 | pass | Confirmed |
| C2 | +0.0426 [-0.0472, +0.1323] | -0.0321 | 0.17111 | 0.3065 | fail | Inconclusive |

Observations dropped only because a later price is missing (end of window is expected; internal would mean selection depends on the future, and is listed):

- B: end of window 345, internal 0
- C1: end of window 472, internal 0
- C2: end of window 184, internal 0

## Exploratory: long-only crypto (not a test; ranking significance is not investable proof)

- base 0.20%: top third -15.6% a year (max drawdown -63%, one-way turnover 13.2x a year); equal weight -32.5% (max drawdown -64%); excess +20.1% [-19.6, +66.1]
  - against Bitcoin bought and held: -13.5% a year (max drawdown -53%); excess +6.6% [-57.1, +79.8]
- stress 0.50%: top third -22.0% a year (max drawdown -65%, one-way turnover 13.2x a year); equal weight -32.9% (max drawdown -65%); excess +12.8% [-27.3, +58.9]
  - against Bitcoin bought and held: -13.5% a year (max drawdown -53%); excess -1.3% [-65.2, +71.9]

## Exploratory: expected-move calibration with the frozen k (target 50% / 80%, tolerance 5 points)

- stock: 49.8% / 80.5%
- crypto: 51.3% / 84.0%

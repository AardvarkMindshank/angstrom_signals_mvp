# Research run: development period

Generated 2026-10-31T08:52 UTC. Hold-out starts 2024-10-30 and was NOT used. Every result below is from earlier dates only.

> Survivor bias: the universe is today's large companies and long-lived coins. Firms and coins that shrank or died are missing, so results lean towards winners. Point-in-time membership was not available from free data.

Stocks (3): AAPL, MSFT, NVDA
Crypto (3): BTC-USD, ETH-USD, XRP-USD

Parity check: 48 sampled days scored from the last 200 bars against all history; largest difference 0.00 points.

Tests counted: 572. At a 5% false-alarm rate about 29 would pass by luck alone.

## 1. How often the score reaches each level

| Class | Days | 10th pct | Median | 90th pct | 70+ | 80+ | 30 or less | 20 or less | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stock | 6939 | 30 | 64 | 74 | 29.1% | 1.7% | 9.7% | 1.0% | 13 | 89 |
| crypto | 9608 | 25 | 49 | 74 | 21.0% | 2.0% | 22.3% | 2.7% | 10 | 88 |

Score distribution, all assets of a class (days per 10-point band):

- stock: 0-9: 0, 10-19: 65, 20-29: 589, 30-39: 830, 40-49: 633, 50-59: 834, 60-69: 1967, 70-79: 1903, 80-89: 118, 90-100: 0
- crypto: 0-9: 0, 10-19: 250, 20-29: 1818, 30-39: 1806, 40-49: 987, 50-59: 1044, 60-69: 1682, 70-79: 1828, 80-89: 193, 90-100: 0

## 2. Signals: score, families and single factors

Each cell: estimate [95% band]. Time series = each asset against its own history, pooled. Cross-section = assets ranked against their own class each day. Ranking = top third minus bottom third, % return. Positive means more points came before better returns.

### stock

| Signal | Horizon | Time series | Cross-section | Ranking (%) |
| --- | --- | --- | --- | --- |
| score | 1d | -0.008 [-0.039, +0.025] (noise) | too few (too few) | too few (too few) |
| score | 3d | -0.006 [-0.052, +0.052] (noise) | too few (too few) | too few (too few) |
| score | 7d | -0.007 [-0.079, +0.076] (noise) | too few (too few) | too few (too few) |
| score | 14d | -0.002 [-0.097, +0.103] (noise) | too few (too few) | too few (too few) |
| score | 30d | -0.006 [-0.122, +0.118] (noise) | too few (too few) | too few (too few) |
| Trend | 1d | -0.016 [-0.045, +0.016] (noise) | too few (too few) | too few (too few) |
| Trend | 3d | -0.008 [-0.057, +0.051] (noise) | too few (too few) | too few (too few) |
| Trend | 7d | -0.008 [-0.081, +0.074] (noise) | too few (too few) | too few (too few) |
| Trend | 14d | -0.012 [-0.115, +0.097] (noise) | too few (too few) | too few (too few) |
| Trend | 30d | -0.026 [-0.154, +0.104] (noise) | too few (too few) | too few (too few) |
| Stretch | 1d | +0.024 [-0.006, +0.052] (noise) | too few (too few) | too few (too few) |
| Stretch | 3d | +0.011 [-0.038, +0.059] (noise) | too few (too few) | too few (too few) |
| Stretch | 7d | +0.010 [-0.066, +0.078] (noise) | too few (too few) | too few (too few) |
| Stretch | 14d | +0.018 [-0.085, +0.099] (noise) | too few (too few) | too few (too few) |
| Stretch | 30d | +0.045 [-0.081, +0.156] (noise) | too few (too few) | too few (too few) |
| Flow | 1d | -0.016 [-0.043, +0.016] (noise) | too few (too few) | too few (too few) |
| Flow | 3d | -0.013 [-0.056, +0.033] (noise) | too few (too few) | too few (too few) |
| Flow | 7d | -0.007 [-0.064, +0.058] (noise) | too few (too few) | too few (too few) |
| Flow | 14d | -0.005 [-0.082, +0.076] (noise) | too few (too few) | too few (too few) |
| Flow | 30d | -0.025 [-0.121, +0.080] (noise) | too few (too few) | too few (too few) |
| RSI | 1d | +0.021 [-0.008, +0.051] (noise) | too few (too few) | too few (too few) |
| RSI | 3d | +0.010 [-0.042, +0.056] (noise) | too few (too few) | too few (too few) |
| RSI | 7d | +0.009 [-0.064, +0.075] (noise) | too few (too few) | too few (too few) |
| RSI | 14d | +0.015 [-0.092, +0.104] (noise) | too few (too few) | too few (too few) |
| RSI | 30d | +0.046 [-0.099, +0.168] (noise) | too few (too few) | too few (too few) |
| Stochastic | 1d | +0.020 [-0.011, +0.050] (noise) | too few (too few) | too few (too few) |
| Stochastic | 3d | +0.011 [-0.038, +0.058] (noise) | too few (too few) | too few (too few) |
| Stochastic | 7d | +0.010 [-0.059, +0.076] (noise) | too few (too few) | too few (too few) |
| Stochastic | 14d | +0.026 [-0.064, +0.102] (noise) | too few (too few) | too few (too few) |
| Stochastic | 30d | +0.041 [-0.053, +0.128] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 1d | -0.007 [-0.039, +0.026] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 3d | -0.005 [-0.059, +0.051] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 7d | -0.010 [-0.087, +0.078] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 14d | -0.007 [-0.109, +0.112] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 30d | -0.006 [-0.120, +0.129] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 1d | -0.005 [-0.029, +0.021] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 3d | -0.016 [-0.058, +0.027] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 7d | -0.015 [-0.077, +0.059] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 14d | -0.015 [-0.105, +0.077] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 30d | -0.020 [-0.153, +0.113] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 1d | -0.020 [-0.050, +0.011] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 3d | -0.007 [-0.056, +0.045] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 7d | -0.003 [-0.075, +0.072] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 14d | +0.003 [-0.077, +0.094] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 30d | -0.016 [-0.111, +0.093] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 1d | -0.018 [-0.047, +0.015] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 3d | -0.018 [-0.068, +0.042] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 7d | -0.024 [-0.099, +0.059] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 14d | -0.030 [-0.133, +0.089] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 30d | -0.031 [-0.168, +0.114] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 1d | +0.029 [-0.000, +0.056] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 3d | +0.013 [-0.032, +0.056] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 7d | +0.008 [-0.056, +0.067] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 14d | +0.006 [-0.078, +0.078] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 30d | +0.031 [-0.073, +0.114] (noise) | too few (too few) | too few (too few) |
| Volume | 1d | -0.003 [-0.036, +0.029] (noise) | too few (too few) | too few (too few) |
| Volume | 3d | -0.004 [-0.034, +0.024] (noise) | too few (too few) | too few (too few) |
| Volume | 7d | +0.001 [-0.030, +0.029] (noise) | too few (too few) | too few (too few) |
| Volume | 14d | -0.003 [-0.030, +0.022] (noise) | too few (too few) | too few (too few) |
| Volume | 30d | -0.007 [-0.036, +0.022] (noise) | too few (too few) | too few (too few) |
| OBV | 1d | -0.015 [-0.041, +0.017] (noise) | too few (too few) | too few (too few) |
| OBV | 3d | -0.011 [-0.057, +0.037] (noise) | too few (too few) | too few (too few) |
| OBV | 7d | -0.007 [-0.067, +0.066] (noise) | too few (too few) | too few (too few) |
| OBV | 14d | -0.003 [-0.088, +0.088] (noise) | too few (too few) | too few (too few) |
| OBV | 30d | -0.025 [-0.127, +0.092] (noise) | too few (too few) | too few (too few) |
| Performance | 1d | -0.018 [-0.048, +0.013] (noise) | too few (too few) | too few (too few) |
| Performance | 3d | +0.005 [-0.043, +0.049] (noise) | too few (too few) | too few (too few) |
| Performance | 7d | +0.002 [-0.062, +0.073] (noise) | too few (too few) | too few (too few) |
| Performance | 14d | -0.007 [-0.079, +0.071] (noise) | too few (too few) | too few (too few) |
| Performance | 30d | -0.023 [-0.095, +0.061] (noise) | too few (too few) | too few (too few) |

### crypto

| Signal | Horizon | Time series | Cross-section | Ranking (%) |
| --- | --- | --- | --- | --- |
| score | 1d | +0.031 [+0.004, +0.059] (positive) | too few (too few) | too few (too few) |
| score | 3d | +0.032 [-0.013, +0.081] (noise) | too few (too few) | too few (too few) |
| score | 7d | +0.027 [-0.036, +0.097] (noise) | too few (too few) | too few (too few) |
| score | 14d | +0.023 [-0.062, +0.106] (noise) | too few (too few) | too few (too few) |
| score | 30d | +0.005 [-0.094, +0.117] (noise) | too few (too few) | too few (too few) |
| Trend | 1d | +0.031 [+0.003, +0.062] (positive) | too few (too few) | too few (too few) |
| Trend | 3d | +0.036 [-0.011, +0.087] (noise) | too few (too few) | too few (too few) |
| Trend | 7d | +0.031 [-0.032, +0.104] (noise) | too few (too few) | too few (too few) |
| Trend | 14d | +0.033 [-0.051, +0.118] (noise) | too few (too few) | too few (too few) |
| Trend | 30d | +0.015 [-0.078, +0.124] (noise) | too few (too few) | too few (too few) |
| Stretch | 1d | -0.028 [-0.059, +0.000] (noise) | too few (too few) | too few (too few) |
| Stretch | 3d | -0.030 [-0.080, +0.017] (noise) | too few (too few) | too few (too few) |
| Stretch | 7d | -0.030 [-0.094, +0.033] (noise) | too few (too few) | too few (too few) |
| Stretch | 14d | -0.042 [-0.124, +0.039] (noise) | too few (too few) | too few (too few) |
| Stretch | 30d | -0.027 [-0.117, +0.054] (noise) | too few (too few) | too few (too few) |
| Flow | 1d | +0.019 [-0.008, +0.045] (noise) | too few (too few) | too few (too few) |
| Flow | 3d | +0.013 [-0.027, +0.051] (noise) | too few (too few) | too few (too few) |
| Flow | 7d | -0.002 [-0.048, +0.049] (noise) | too few (too few) | too few (too few) |
| Flow | 14d | +0.000 [-0.062, +0.064] (noise) | too few (too few) | too few (too few) |
| Flow | 30d | -0.001 [-0.065, +0.062] (noise) | too few (too few) | too few (too few) |
| RSI | 1d | -0.029 [-0.064, -0.000] (negative) | too few (too few) | too few (too few) |
| RSI | 3d | -0.029 [-0.079, +0.019] (noise) | too few (too few) | too few (too few) |
| RSI | 7d | -0.023 [-0.089, +0.042] (noise) | too few (too few) | too few (too few) |
| RSI | 14d | -0.029 [-0.110, +0.052] (noise) | too few (too few) | too few (too few) |
| RSI | 30d | -0.016 [-0.119, +0.075] (noise) | too few (too few) | too few (too few) |
| Stochastic | 1d | -0.022 [-0.050, +0.006] (noise) | too few (too few) | too few (too few) |
| Stochastic | 3d | -0.032 [-0.077, +0.014] (noise) | too few (too few) | too few (too few) |
| Stochastic | 7d | -0.039 [-0.098, +0.015] (noise) | too few (too few) | too few (too few) |
| Stochastic | 14d | -0.054 [-0.131, +0.020] (noise) | too few (too few) | too few (too few) |
| Stochastic | 30d | -0.039 [-0.107, +0.028] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 1d | +0.032 [+0.003, +0.063] (positive) | too few (too few) | too few (too few) |
| Moving Averages | 3d | +0.030 [-0.018, +0.082] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 7d | +0.023 [-0.039, +0.097] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 14d | +0.025 [-0.071, +0.116] (noise) | too few (too few) | too few (too few) |
| Moving Averages | 30d | +0.011 [-0.102, +0.132] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 1d | +0.029 [+0.001, +0.056] (positive) | too few (too few) | too few (too few) |
| ADX Trend | 3d | +0.031 [-0.016, +0.083] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 7d | +0.033 [-0.035, +0.099] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 14d | +0.021 [-0.063, +0.110] (noise) | too few (too few) | too few (too few) |
| ADX Trend | 30d | +0.004 [-0.099, +0.122] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 1d | +0.030 [+0.002, +0.059] (positive) | too few (too few) | too few (too few) |
| MACD & Hist | 3d | +0.044 [-0.001, +0.090] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 7d | +0.035 [-0.029, +0.096] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 14d | +0.042 [-0.034, +0.122] (noise) | too few (too few) | too few (too few) |
| MACD & Hist | 30d | +0.028 [-0.042, +0.106] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 1d | +0.024 [-0.003, +0.055] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 3d | +0.032 [-0.016, +0.083] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 7d | +0.036 [-0.029, +0.100] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 14d | +0.025 [-0.054, +0.116] (noise) | too few (too few) | too few (too few) |
| Ichimoku Cloud | 30d | -0.003 [-0.113, +0.112] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 1d | -0.022 [-0.056, +0.008] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 3d | -0.030 [-0.080, +0.014] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 7d | -0.024 [-0.089, +0.034] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 14d | -0.043 [-0.115, +0.025] (noise) | too few (too few) | too few (too few) |
| Bollinger Bands | 30d | -0.037 [-0.110, +0.025] (noise) | too few (too few) | too few (too few) |
| Volume | 1d | +0.018 [-0.012, +0.045] (noise) | too few (too few) | too few (too few) |
| Volume | 3d | +0.009 [-0.019, +0.038] (noise) | too few (too few) | too few (too few) |
| Volume | 7d | +0.013 [-0.014, +0.043] (noise) | too few (too few) | too few (too few) |
| Volume | 14d | +0.016 [-0.014, +0.046] (noise) | too few (too few) | too few (too few) |
| Volume | 30d | +0.023 [-0.002, +0.046] (noise) | too few (too few) | too few (too few) |
| OBV | 1d | +0.014 [-0.011, +0.039] (noise) | too few (too few) | too few (too few) |
| OBV | 3d | +0.011 [-0.030, +0.049] (noise) | too few (too few) | too few (too few) |
| OBV | 7d | -0.007 [-0.054, +0.051] (noise) | too few (too few) | too few (too few) |
| OBV | 14d | -0.006 [-0.070, +0.061] (noise) | too few (too few) | too few (too few) |
| OBV | 30d | -0.011 [-0.082, +0.055] (noise) | too few (too few) | too few (too few) |
| Performance | 1d | +0.003 [-0.026, +0.031] (noise) | too few (too few) | too few (too few) |
| Performance | 3d | -0.001 [-0.048, +0.049] (noise) | too few (too few) | too few (too few) |
| Performance | 7d | +0.001 [-0.053, +0.055] (noise) | too few (too few) | too few (too few) |
| Performance | 14d | +0.035 [-0.030, +0.104] (noise) | too few (too few) | too few (too few) |
| Performance | 30d | +0.042 [-0.009, +0.108] (noise) | too few (too few) | too few (too few) |

## 3. Extremes

Average forward return on those days minus the asset's own average, % [95% band], and how many days.

### stock

| Rule | 1d | 3d | 7d | 14d | 30d |
| --- | --- | --- | --- | --- | --- |
| top 10% of own scores | +0.08 [-0.11, +0.30] n=553 | +0.26 [-0.19, +0.70] n=553 | +0.57 [-0.30, +1.39] n=553 | +0.82 [-0.99, +2.35] n=553 | +1.27 [-1.32, +3.71] n=553 |
| bottom 10% of own scores | +0.05 [-0.29, +0.36] n=551 | +0.09 [-0.67, +0.86] n=551 | +0.16 [-1.32, +1.80] n=551 | -0.48 [-3.16, +2.47] n=551 | -1.10 [-5.86, +5.32] n=551 |
| score 80 or more | +0.37 [-0.07, +0.85] n=95 | +0.51 [-0.10, +1.21] n=95 | +0.53 [-0.95, +2.20] n=95 | +1.31 [-1.40, +3.74] n=95 | +2.80 [-0.26, +5.42] n=95 |
| score 20 or less | +0.31 [-0.48, +0.94] n=54 | +0.92 [-1.37, +2.73] n=54 | +1.78 [-2.70, +5.16] n=54 | +1.03 [-6.44, +7.00] n=54 | -4.77 [-12.15, +5.85] n=54 |
| score 70 or more | +0.00 [-0.11, +0.13] n=1659 | +0.07 [-0.25, +0.38] n=1659 | +0.12 [-0.63, +0.88] n=1659 | +0.22 [-1.41, +1.56] n=1659 | +0.30 [-2.18, +2.64] n=1659 |
| score 30 or less | +0.06 [-0.27, +0.39] n=491 | +0.11 [-0.71, +0.91] n=491 | +0.19 [-1.49, +1.96] n=491 | -0.60 [-3.33, +2.62] n=491 | -1.39 [-6.30, +5.10] n=491 |
| trend up, stretched down (pullback) | too few n=0 | too few n=0 | too few n=0 | too few n=0 | too few n=0 |
| trend down, stretched up (bounce) | too few n=0 | too few n=0 | too few n=0 | too few n=0 | too few n=0 |

### crypto

| Rule | 1d | 3d | 7d | 14d | 30d |
| --- | --- | --- | --- | --- | --- |
| top 10% of own scores | +0.40 [-0.02, +0.76] n=895 | +1.07 [-0.02, +2.00] n=895 | +2.07 [-0.42, +4.57] n=895 | +3.61 [-1.12, +8.93] n=895 | +1.82 [-6.13, +9.71] n=895 |
| bottom 10% of own scores | -0.12 [-0.41, +0.18] n=751 | -0.19 [-1.02, +0.69] n=751 | -0.14 [-2.13, +1.94] n=751 | -0.71 [-4.13, +2.55] n=751 | -2.58 [-8.88, +4.10] n=751 |
| score 80 or more | -0.20 [-1.12, +0.52] n=160 | -0.03 [-1.92, +1.68] n=160 | -1.11 [-4.05, +1.72] n=160 | +0.29 [-6.81, +9.31] n=160 | -7.36 [-16.02, +3.82] n=160 |
| score 20 or less | -0.00 [-0.52, +0.55] n=200 | -0.22 [-1.30, +1.03] n=200 | +0.02 [-2.93, +4.03] n=200 | -0.34 [-4.31, +4.01] n=200 | -5.15 [-9.92, +0.32] n=200 |
| score 70 or more | +0.32 [+0.01, +0.59] n=1658 | +0.89 [-0.06, +1.72] n=1658 | +1.72 [-0.37, +3.82] n=1658 | +2.67 [-1.18, +6.76] n=1658 | +0.58 [-7.52, +8.24] n=1658 |
| score 30 or less | -0.14 [-0.40, +0.11] n=1626 | -0.22 [-0.89, +0.51] n=1626 | -0.49 [-1.97, +1.07] n=1626 | -1.25 [-4.13, +1.57] n=1626 | -3.38 [-8.83, +2.19] n=1626 |
| trend up, stretched down (pullback) | too few n=0 | too few n=0 | too few n=0 | too few n=0 | too few n=0 |
| trend down, stretched up (bounce) | +0.70 [+0.70, +0.70] n=1 | -0.56 [-0.56, -0.56] n=1 | -3.96 [-3.96, -3.96] n=1 | +3.95 [+3.95, +3.95] n=1 | -10.04 [-10.04, -10.04] n=1 |

## 4. Regimes

Pooled time-series rank correlation inside each condition [95% band].

### stock

| Signal | Condition | 7d | 14d | 30d |
| --- | --- | --- | --- | --- |
| Trend | asset trending (ADX 25+) | +0.005 [-0.092, +0.099] | +0.028 [-0.111, +0.161] | -0.003 [-0.182, +0.193] |
| Trend | asset ranging (ADX under 20) | +0.008 [-0.097, +0.132] | -0.014 [-0.149, +0.126] | -0.006 [-0.157, +0.152] |
| Trend | benchmark above 200-day | -0.039 [-0.109, +0.040] | -0.058 [-0.150, +0.044] | -0.089 [-0.210, +0.041] |
| Trend | benchmark below 200-day | +0.023 [-0.122, +0.183] | +0.049 [-0.168, +0.235] | +0.065 [-0.193, +0.385] |
| Stretch | asset trending (ADX 25+) | -0.008 [-0.099, +0.078] | -0.024 [-0.149, +0.096] | +0.011 [-0.165, +0.184] |
| Stretch | asset ranging (ADX under 20) | -0.014 [-0.138, +0.089] | +0.011 [-0.110, +0.118] | +0.036 [-0.102, +0.173] |
| Stretch | benchmark above 200-day | +0.030 [-0.043, +0.097] | +0.054 [-0.049, +0.140] | +0.088 [-0.035, +0.203] |
| Stretch | benchmark below 200-day | -0.029 [-0.159, +0.106] | -0.059 [-0.222, +0.114] | -0.028 [-0.318, +0.198] |
| score | asset trending (ADX 25+) | +0.005 [-0.101, +0.101] | +0.040 [-0.103, +0.173] | +0.020 [-0.146, +0.210] |
| score | asset ranging (ADX under 20) | +0.007 [-0.091, +0.129] | -0.013 [-0.128, +0.121] | -0.001 [-0.138, +0.157] |
| score | benchmark above 200-day | -0.042 [-0.111, +0.040] | -0.050 [-0.137, +0.041] | -0.069 [-0.180, +0.044] |
| score | benchmark below 200-day | +0.020 [-0.129, +0.179] | +0.036 [-0.178, +0.227] | +0.073 [-0.164, +0.388] |

### crypto

| Signal | Condition | 7d | 14d | 30d |
| --- | --- | --- | --- | --- |
| Trend | asset trending (ADX 25+) | +0.034 [-0.056, +0.119] | +0.032 [-0.072, +0.138] | +0.010 [-0.110, +0.143] |
| Trend | asset ranging (ADX under 20) | -0.006 [-0.108, +0.108] | +0.015 [-0.111, +0.130] | +0.051 [-0.086, +0.182] |
| Trend | benchmark above 200-day | +0.055 [-0.025, +0.133] | +0.043 [-0.039, +0.137] | -0.006 [-0.104, +0.117] |
| Trend | benchmark below 200-day | -0.040 [-0.152, +0.062] | -0.028 [-0.172, +0.109] | -0.035 [-0.183, +0.125] |
| Stretch | asset trending (ADX 25+) | -0.019 [-0.098, +0.068] | -0.029 [-0.136, +0.078] | -0.005 [-0.115, +0.098] |
| Stretch | asset ranging (ADX under 20) | -0.050 [-0.161, +0.053] | -0.043 [-0.158, +0.062] | -0.055 [-0.159, +0.044] |
| Stretch | benchmark above 200-day | -0.043 [-0.123, +0.037] | -0.050 [-0.149, +0.032] | -0.011 [-0.117, +0.085] |
| Stretch | benchmark below 200-day | +0.013 [-0.078, +0.121] | +0.003 [-0.132, +0.130] | +0.005 [-0.148, +0.137] |
| score | asset trending (ADX 25+) | +0.038 [-0.045, +0.122] | +0.030 [-0.070, +0.130] | +0.011 [-0.113, +0.144] |
| score | asset ranging (ADX under 20) | -0.030 [-0.120, +0.070] | -0.010 [-0.136, +0.103] | +0.032 [-0.103, +0.168] |
| score | benchmark above 200-day | +0.038 [-0.037, +0.108] | +0.027 [-0.048, +0.107] | -0.019 [-0.110, +0.105] |
| score | benchmark below 200-day | -0.039 [-0.149, +0.059] | -0.038 [-0.171, +0.083] | -0.042 [-0.184, +0.107] |

## 5. Volatility (ATR%)

Mean partial rank correlation of ATR% with the size of later moves, after trailing volatility; and how many assets clear their own noise band.

- stock, 1d: mean +0.159, 3 of 3 assets clear the band
- stock, 7d: mean +0.317, 3 of 3 assets clear the band
- stock, 14d: mean +0.321, 3 of 3 assets clear the band
- crypto, 1d: mean +0.086, 3 of 3 assets clear the band
- crypto, 7d: mean +0.194, 3 of 3 assets clear the band
- crypto, 14d: mean +0.220, 3 of 3 assets clear the band

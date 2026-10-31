# Research run: development period

Generated 2026-10-31T10:40 UTC. Hold-out starts 2024-10-30 and was NOT used. Every result below is from earlier dates only.

Method v2: prices on or after the hold-out start are removed before scoring, so forward-return labels and the score histogram stop at the boundary. The first run (method v1, 31 Oct 2026) let the last development labels use up to 31 bars of hold-out prices; its report is kept unchanged on the reports branch.

> Survivor bias: the universe is today's large companies and long-lived coins. Firms and coins that shrank or died are missing, so results lean towards winners. Point-in-time membership was not available from free data.

Stocks (61): AAPL, ABBV, ADBE, AMD, AMGN, AMT, AMZN, AXP, BA, BAC, C, CAT, COP, COST, CRM, CSCO, CVX, DE, DIS, DUK, FCX, GE, GOOGL, GS, HD, HON, IBM, INTC, JNJ, JPM, KO, LIN, LLY, LMT, MCD, META, MRK, MS, MSFT, NEE, NEM, NFLX, NKE, NVDA, ORCL, PEP, PFE, PG, QCOM, SBUX, SLB, SPG, T, TSLA, TXN, UNH, UPS, VZ, WFC, WMT, XOM
Crypto (25): ADA-USD, ALGO-USD, ATOM-USD, AVAX-USD, BCH-USD, BNB-USD, BTC-USD, DASH-USD, DOGE-USD, DOT-USD, EOS-USD, ETC-USD, ETH-USD, FIL-USD, LINK-USD, LTC-USD, NEO-USD, SOL-USD, TRX-USD, VET-USD, XLM-USD, XMR-USD, XRP-USD, XTZ-USD, ZEC-USD

Parity check: 44 sampled days scored from the last 90 bars against all history; largest difference 4.00 points.
Parity check: 48 sampled days scored from the last 200 bars against all history; largest difference 0.00 points.
Parity check: 48 sampled days scored from the last 365 bars against all history; largest difference 0.00 points.

Tests counted: 572. At a 5% false-alarm rate about 29 would pass by luck alone.

## 1. How often the score reaches each level

| Class | Days | 10th pct | Median | 90th pct | 70+ | 80+ | 30 or less | 20 or less | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stock | 110532 | 28 | 60 | 74 | 24.8% | 1.8% | 13.3% | 1.5% | 10 | 89 |
| crypto | 55099 | 25 | 45 | 75 | 20.0% | 3.4% | 22.8% | 3.0% | 10 | 93 |

Score distribution, all assets of a class (days per 10-point band):

- stock: 0-9: 0, 10-19: 1603, 20-29: 12676, 30-39: 17278, 40-49: 11229, 50-59: 13079, 60-69: 27266, 70-79: 25397, 80-89: 2004, 90-100: 0
- crypto: 0-9: 0, 10-19: 1572, 20-29: 10556, 30-39: 11281, 40-49: 6564, 50-59: 5622, 60-69: 8508, 70-79: 9118, 80-89: 1867, 90-100: 11

## 2. Signals: score, families and single factors

Each cell: estimate [95% band]. Time series = each asset against its own history, pooled. Cross-section = assets ranked against their own class each day. Ranking = top third minus bottom third, % return. Positive means more points came before better returns.

### stock

| Signal | Horizon | Time series | Cross-section | Ranking (%) |
| --- | --- | --- | --- | --- |
| score | 1d | -0.012 [-0.025, +0.004] (noise) | +0.003 [-0.005, +0.012] (noise) | +0.00 [-0.03, +0.04] (noise) |
| score | 3d | -0.024 [-0.047, +0.000] (noise) | +0.003 [-0.011, +0.017] (noise) | +0.04 [-0.06, +0.15] (noise) |
| score | 7d | -0.040 [-0.072, -0.007] (negative) | +0.003 [-0.016, +0.022] (noise) | +0.06 [-0.17, +0.28] (noise) |
| score | 14d | -0.059 [-0.097, -0.020] (negative) | -0.005 [-0.030, +0.024] (noise) | -0.01 [-0.43, +0.48] (noise) |
| score | 30d | -0.084 [-0.134, -0.035] (negative) | -0.013 [-0.045, +0.022] (noise) | -0.15 [-0.89, +0.80] (noise) |
| Trend | 1d | -0.012 [-0.027, +0.004] (noise) | +0.007 [-0.003, +0.017] (noise) | +0.00 [-0.04, +0.04] (noise) |
| Trend | 3d | -0.025 [-0.048, +0.000] (noise) | +0.005 [-0.011, +0.018] (noise) | +0.03 [-0.09, +0.13] (noise) |
| Trend | 7d | -0.040 [-0.075, -0.005] (negative) | +0.005 [-0.015, +0.025] (noise) | +0.05 [-0.18, +0.26] (noise) |
| Trend | 14d | -0.057 [-0.096, -0.019] (negative) | -0.000 [-0.024, +0.030] (noise) | -0.01 [-0.40, +0.49] (noise) |
| Trend | 30d | -0.086 [-0.135, -0.038] (negative) | -0.008 [-0.044, +0.029] (noise) | -0.15 [-0.99, +0.80] (noise) |
| Stretch | 1d | +0.011 [-0.004, +0.025] (noise) | -0.008 [-0.018, +0.001] (noise) | -0.02 [-0.06, +0.02] (noise) |
| Stretch | 3d | +0.022 [-0.001, +0.043] (noise) | -0.003 [-0.017, +0.010] (noise) | -0.04 [-0.16, +0.06] (noise) |
| Stretch | 7d | +0.031 [+0.001, +0.063] (positive) | -0.001 [-0.022, +0.018] (noise) | -0.08 [-0.29, +0.13] (noise) |
| Stretch | 14d | +0.044 [+0.011, +0.076] (positive) | +0.001 [-0.022, +0.024] (noise) | -0.12 [-0.49, +0.21] (noise) |
| Stretch | 30d | +0.074 [+0.034, +0.112] (positive) | +0.008 [-0.024, +0.040] (noise) | -0.01 [-0.77, +0.69] (noise) |
| Flow | 1d | -0.012 [-0.024, +0.003] (noise) | -0.004 [-0.012, +0.003] (noise) | -0.03 [-0.07, +0.00] (noise) |
| Flow | 3d | -0.020 [-0.038, -0.003] (negative) | -0.006 [-0.017, +0.006] (noise) | -0.07 [-0.16, +0.02] (noise) |
| Flow | 7d | -0.028 [-0.053, -0.004] (negative) | -0.001 [-0.016, +0.015] (noise) | -0.14 [-0.32, +0.06] (noise) |
| Flow | 14d | -0.042 [-0.069, -0.014] (negative) | -0.006 [-0.024, +0.013] (noise) | -0.34 [-0.68, +0.05] (noise) |
| Flow | 30d | -0.066 [-0.096, -0.032] (negative) | -0.016 [-0.039, +0.008] (noise) | -0.80 [-1.49, +0.03] (noise) |
| RSI | 1d | +0.012 [-0.003, +0.026] (noise) | -0.008 [-0.018, +0.001] (noise) | -0.02 [-0.06, +0.01] (noise) |
| RSI | 3d | +0.025 [+0.001, +0.045] (positive) | -0.004 [-0.019, +0.010] (noise) | -0.06 [-0.17, +0.04] (noise) |
| RSI | 7d | +0.036 [+0.004, +0.068] (positive) | -0.004 [-0.025, +0.016] (noise) | -0.14 [-0.37, +0.08] (noise) |
| RSI | 14d | +0.052 [+0.016, +0.088] (positive) | +0.001 [-0.026, +0.024] (noise) | -0.22 [-0.63, +0.12] (noise) |
| RSI | 30d | +0.082 [+0.037, +0.128] (positive) | +0.009 [-0.026, +0.043] (noise) | -0.23 [-1.13, +0.52] (noise) |
| Stochastic | 1d | +0.009 [-0.003, +0.021] (noise) | -0.006 [-0.014, +0.002] (noise) | -0.04 [-0.07, -0.00] (negative) |
| Stochastic | 3d | +0.018 [-0.001, +0.038] (noise) | +0.001 [-0.012, +0.013] (noise) | -0.07 [-0.18, +0.02] (noise) |
| Stochastic | 7d | +0.022 [-0.005, +0.051] (noise) | +0.002 [-0.016, +0.020] (noise) | -0.14 [-0.37, +0.05] (noise) |
| Stochastic | 14d | +0.031 [+0.000, +0.060] (positive) | +0.000 [-0.021, +0.021] (noise) | -0.28 [-0.65, +0.07] (noise) |
| Stochastic | 30d | +0.055 [+0.024, +0.086] (positive) | +0.004 [-0.022, +0.031] (noise) | -0.51 [-1.22, +0.20] (noise) |
| Moving Averages | 1d | -0.010 [-0.024, +0.005] (noise) | +0.009 [-0.001, +0.019] (noise) | +0.00 [-0.04, +0.04] (noise) |
| Moving Averages | 3d | -0.026 [-0.049, -0.002] (negative) | +0.006 [-0.008, +0.020] (noise) | +0.01 [-0.11, +0.12] (noise) |
| Moving Averages | 7d | -0.042 [-0.074, -0.006] (negative) | +0.002 [-0.019, +0.023] (noise) | -0.05 [-0.30, +0.19] (noise) |
| Moving Averages | 14d | -0.062 [-0.103, -0.022] (negative) | -0.005 [-0.030, +0.027] (noise) | -0.23 [-0.65, +0.21] (noise) |
| Moving Averages | 30d | -0.089 [-0.141, -0.041] (negative) | -0.010 [-0.045, +0.032] (noise) | -0.53 [-1.37, +0.44] (noise) |
| ADX Trend | 1d | -0.010 [-0.022, +0.004] (noise) | +0.006 [-0.002, +0.014] (noise) | -0.01 [-0.04, +0.03] (noise) |
| ADX Trend | 3d | -0.023 [-0.045, -0.001] (negative) | +0.003 [-0.011, +0.015] (noise) | -0.02 [-0.13, +0.09] (noise) |
| ADX Trend | 7d | -0.033 [-0.064, +0.001] (noise) | +0.006 [-0.014, +0.024] (noise) | -0.04 [-0.29, +0.20] (noise) |
| ADX Trend | 14d | -0.042 [-0.079, -0.003] (negative) | +0.004 [-0.020, +0.029] (noise) | -0.13 [-0.60, +0.34] (noise) |
| ADX Trend | 30d | -0.058 [-0.113, -0.006] (negative) | +0.005 [-0.029, +0.039] (noise) | -0.31 [-1.15, +0.65] (noise) |
| MACD & Hist | 1d | -0.006 [-0.019, +0.008] (noise) | +0.000 [-0.008, +0.010] (noise) | -0.01 [-0.05, +0.03] (noise) |
| MACD & Hist | 3d | -0.008 [-0.029, +0.014] (noise) | -0.003 [-0.017, +0.011] (noise) | -0.01 [-0.11, +0.10] (noise) |
| MACD & Hist | 7d | -0.015 [-0.049, +0.015] (noise) | +0.001 [-0.018, +0.022] (noise) | -0.05 [-0.24, +0.16] (noise) |
| MACD & Hist | 14d | -0.029 [-0.060, +0.005] (noise) | +0.002 [-0.020, +0.024] (noise) | -0.13 [-0.51, +0.25] (noise) |
| MACD & Hist | 30d | -0.054 [-0.082, -0.023] (negative) | -0.006 [-0.030, +0.019] (noise) | -0.67 [-1.38, +0.09] (noise) |
| Ichimoku Cloud | 1d | -0.013 [-0.027, +0.002] (noise) | +0.006 [-0.002, +0.015] (noise) | -0.02 [-0.07, +0.02] (noise) |
| Ichimoku Cloud | 3d | -0.030 [-0.054, -0.004] (negative) | +0.002 [-0.012, +0.017] (noise) | -0.05 [-0.17, +0.05] (noise) |
| Ichimoku Cloud | 7d | -0.049 [-0.081, -0.012] (negative) | -0.003 [-0.022, +0.016] (noise) | -0.15 [-0.41, +0.08] (noise) |
| Ichimoku Cloud | 14d | -0.067 [-0.109, -0.023] (negative) | -0.010 [-0.038, +0.021] (noise) | -0.41 [-0.83, +0.03] (noise) |
| Ichimoku Cloud | 30d | -0.089 [-0.146, -0.037] (negative) | -0.015 [-0.051, +0.025] (noise) | -0.80 [-1.66, +0.06] (noise) |
| Bollinger Bands | 1d | +0.008 [-0.007, +0.022] (noise) | -0.006 [-0.014, +0.002] (noise) | -0.03 [-0.07, +0.00] (noise) |
| Bollinger Bands | 3d | +0.015 [-0.006, +0.035] (noise) | -0.002 [-0.015, +0.012] (noise) | -0.08 [-0.18, +0.01] (noise) |
| Bollinger Bands | 7d | +0.021 [-0.009, +0.052] (noise) | -0.002 [-0.018, +0.014] (noise) | -0.16 [-0.39, +0.03] (noise) |
| Bollinger Bands | 14d | +0.030 [+0.000, +0.059] (positive) | -0.003 [-0.023, +0.017] (noise) | -0.31 [-0.66, +0.04] (noise) |
| Bollinger Bands | 30d | +0.056 [+0.028, +0.085] (positive) | +0.001 [-0.021, +0.028] (noise) | -0.45 [-1.24, +0.25] (noise) |
| Volume | 1d | -0.004 [-0.017, +0.012] (noise) | -0.006 [-0.014, +0.002] (noise) | -0.05 [-0.09, -0.01] (negative) |
| Volume | 3d | -0.007 [-0.017, +0.003] (noise) | -0.004 [-0.012, +0.003] (noise) | -0.12 [-0.23, -0.01] (negative) |
| Volume | 7d | -0.009 [-0.019, +0.001] (noise) | -0.003 [-0.011, +0.005] (noise) | -0.25 [-0.48, -0.03] (negative) |
| Volume | 14d | -0.009 [-0.021, +0.002] (noise) | -0.007 [-0.014, +0.001] (noise) | -0.47 [-0.94, -0.02] (negative) |
| Volume | 30d | -0.009 [-0.019, +0.001] (noise) | -0.003 [-0.009, +0.004] (noise) | -0.98 [-1.93, -0.04] (negative) |
| OBV | 1d | -0.012 [-0.023, +0.000] (noise) | -0.002 [-0.010, +0.005] (noise) | -0.03 [-0.07, +0.00] (noise) |
| OBV | 3d | -0.020 [-0.038, -0.000] (negative) | -0.003 [-0.014, +0.009] (noise) | -0.07 [-0.17, +0.04] (noise) |
| OBV | 7d | -0.028 [-0.054, -0.002] (negative) | +0.001 [-0.015, +0.018] (noise) | -0.14 [-0.34, +0.08] (noise) |
| OBV | 14d | -0.044 [-0.071, -0.014] (negative) | -0.003 [-0.022, +0.018] (noise) | -0.38 [-0.79, +0.05] (noise) |
| OBV | 30d | -0.070 [-0.102, -0.034] (negative) | -0.014 [-0.039, +0.014] (noise) | -0.96 [-1.79, +0.01] (noise) |
| Performance | 1d | -0.013 [-0.028, +0.002] (noise) | -0.002 [-0.012, +0.011] (noise) | -0.00 [-0.05, +0.05] (noise) |
| Performance | 3d | -0.012 [-0.033, +0.010] (noise) | -0.006 [-0.024, +0.012] (noise) | +0.02 [-0.11, +0.15] (noise) |
| Performance | 7d | -0.012 [-0.047, +0.018] (noise) | -0.001 [-0.023, +0.022] (noise) | +0.10 [-0.11, +0.34] (noise) |
| Performance | 14d | -0.018 [-0.052, +0.015] (noise) | -0.000 [-0.024, +0.023] (noise) | +0.12 [-0.25, +0.48] (noise) |
| Performance | 30d | -0.045 [-0.071, -0.020] (negative) | -0.004 [-0.030, +0.020] (noise) | -0.01 [-0.58, +0.53] (noise) |

### crypto

| Signal | Horizon | Time series | Cross-section | Ranking (%) |
| --- | --- | --- | --- | --- |
| score | 1d | +0.014 [-0.006, +0.034] (noise) | -0.014 [-0.027, -0.004] (negative) | +0.05 [-0.05, +0.13] (noise) |
| score | 3d | +0.015 [-0.022, +0.053] (noise) | -0.007 [-0.024, +0.009] (noise) | +0.19 [-0.04, +0.42] (noise) |
| score | 7d | +0.012 [-0.041, +0.061] (noise) | +0.001 [-0.022, +0.024] (noise) | +0.62 [+0.08, +1.12] (positive) |
| score | 14d | +0.012 [-0.059, +0.074] (noise) | +0.008 [-0.017, +0.036] (noise) | +1.21 [+0.13, +2.26] (positive) |
| score | 30d | +0.011 [-0.066, +0.104] (noise) | +0.000 [-0.028, +0.032] (noise) | +1.73 [+0.27, +3.56] (positive) |
| Trend | 1d | +0.012 [-0.010, +0.034] (noise) | -0.016 [-0.027, -0.005] (negative) | +0.13 [+0.03, +0.22] (positive) |
| Trend | 3d | +0.013 [-0.026, +0.055] (noise) | -0.008 [-0.025, +0.008] (noise) | +0.41 [+0.13, +0.65] (positive) |
| Trend | 7d | +0.010 [-0.045, +0.063] (noise) | -0.004 [-0.030, +0.021] (noise) | +0.84 [+0.22, +1.38] (positive) |
| Trend | 14d | +0.015 [-0.059, +0.083] (noise) | +0.009 [-0.020, +0.043] (noise) | +1.43 [+0.46, +2.40] (positive) |
| Trend | 30d | +0.015 [-0.060, +0.113] (noise) | +0.005 [-0.033, +0.043] (noise) | +2.28 [+0.41, +4.33] (positive) |
| Stretch | 1d | -0.010 [-0.035, +0.013] (noise) | +0.006 [-0.004, +0.016] (noise) | -0.13 [-0.22, -0.03] (negative) |
| Stretch | 3d | -0.011 [-0.057, +0.027] (noise) | +0.000 [-0.014, +0.017] (noise) | -0.40 [-0.62, -0.18] (negative) |
| Stretch | 7d | -0.008 [-0.059, +0.042] (noise) | -0.005 [-0.026, +0.017] (noise) | -0.70 [-1.22, -0.13] (negative) |
| Stretch | 14d | -0.023 [-0.099, +0.045] (noise) | -0.016 [-0.045, +0.012] (noise) | -1.29 [-2.27, -0.39] (negative) |
| Stretch | 30d | -0.029 [-0.103, +0.031] (noise) | -0.015 [-0.050, +0.019] (noise) | -1.41 [-3.10, +0.58] (noise) |
| Flow | 1d | +0.007 [-0.011, +0.025] (noise) | -0.009 [-0.020, -0.000] (negative) | +0.07 [-0.03, +0.16] (noise) |
| Flow | 3d | +0.003 [-0.024, +0.036] (noise) | -0.004 [-0.016, +0.008] (noise) | +0.12 [-0.13, +0.35] (noise) |
| Flow | 7d | -0.009 [-0.048, +0.027] (noise) | -0.001 [-0.018, +0.016] (noise) | +0.12 [-0.38, +0.63] (noise) |
| Flow | 14d | -0.003 [-0.049, +0.049] (noise) | +0.005 [-0.014, +0.025] (noise) | +0.31 [-0.73, +1.31] (noise) |
| Flow | 30d | +0.012 [-0.030, +0.062] (noise) | -0.003 [-0.022, +0.021] (noise) | +0.45 [-1.76, +3.07] (noise) |
| RSI | 1d | -0.011 [-0.034, +0.012] (noise) | +0.006 [-0.004, +0.018] (noise) | -0.12 [-0.21, -0.02] (negative) |
| RSI | 3d | -0.011 [-0.053, +0.028] (noise) | +0.002 [-0.013, +0.018] (noise) | -0.35 [-0.60, -0.10] (negative) |
| RSI | 7d | -0.008 [-0.058, +0.046] (noise) | -0.002 [-0.024, +0.020] (noise) | -0.66 [-1.22, -0.08] (negative) |
| RSI | 14d | -0.017 [-0.088, +0.054] (noise) | -0.008 [-0.037, +0.023] (noise) | -1.10 [-2.06, -0.10] (negative) |
| RSI | 30d | -0.020 [-0.106, +0.050] (noise) | -0.007 [-0.042, +0.031] (noise) | -1.60 [-3.67, +0.93] (noise) |
| Stochastic | 1d | -0.005 [-0.026, +0.016] (noise) | +0.004 [-0.007, +0.015] (noise) | -0.04 [-0.13, +0.05] (noise) |
| Stochastic | 3d | -0.013 [-0.048, +0.021] (noise) | -0.002 [-0.016, +0.013] (noise) | -0.18 [-0.42, +0.04] (noise) |
| Stochastic | 7d | -0.013 [-0.059, +0.027] (noise) | -0.005 [-0.022, +0.015] (noise) | -0.33 [-0.88, +0.23] (noise) |
| Stochastic | 14d | -0.027 [-0.091, +0.030] (noise) | -0.017 [-0.038, +0.006] (noise) | -0.56 [-1.71, +0.55] (noise) |
| Stochastic | 30d | -0.033 [-0.093, +0.011] (noise) | -0.014 [-0.043, +0.013] (noise) | -0.19 [-2.97, +2.41] (noise) |
| Moving Averages | 1d | +0.013 [-0.009, +0.035] (noise) | -0.019 [-0.030, -0.008] (negative) | +0.13 [+0.03, +0.24] (positive) |
| Moving Averages | 3d | +0.016 [-0.023, +0.055] (noise) | -0.010 [-0.029, +0.007] (noise) | +0.30 [+0.06, +0.55] (positive) |
| Moving Averages | 7d | +0.015 [-0.043, +0.065] (noise) | +0.003 [-0.021, +0.025] (noise) | +0.70 [+0.18, +1.27] (positive) |
| Moving Averages | 14d | +0.015 [-0.060, +0.084] (noise) | +0.012 [-0.019, +0.044] (noise) | +1.39 [+0.31, +2.59] (positive) |
| Moving Averages | 30d | +0.012 [-0.073, +0.123] (noise) | +0.005 [-0.030, +0.043] (noise) | +2.48 [-0.42, +5.98] (noise) |
| ADX Trend | 1d | +0.002 [-0.021, +0.021] (noise) | -0.017 [-0.028, -0.005] (negative) | +0.00 [-0.11, +0.11] (noise) |
| ADX Trend | 3d | +0.001 [-0.035, +0.035] (noise) | -0.021 [-0.038, -0.005] (negative) | +0.05 [-0.25, +0.34] (noise) |
| ADX Trend | 7d | +0.005 [-0.046, +0.051] (noise) | -0.018 [-0.042, +0.003] (noise) | +0.27 [-0.32, +0.85] (noise) |
| ADX Trend | 14d | +0.010 [-0.061, +0.077] (noise) | -0.015 [-0.039, +0.010] (noise) | +0.62 [-0.49, +1.83] (noise) |
| ADX Trend | 30d | -0.003 [-0.093, +0.099] (noise) | -0.029 [-0.062, +0.001] (noise) | +0.34 [-2.44, +3.05] (noise) |
| MACD & Hist | 1d | +0.020 [+0.000, +0.041] (positive) | +0.004 [-0.007, +0.016] (noise) | +0.22 [+0.14, +0.35] (positive) |
| MACD & Hist | 3d | +0.022 [-0.010, +0.060] (noise) | +0.018 [+0.002, +0.033] (positive) | +0.52 [+0.26, +0.86] (positive) |
| MACD & Hist | 7d | +0.017 [-0.033, +0.067] (noise) | +0.024 [+0.003, +0.045] (positive) | +0.78 [+0.19, +1.37] (positive) |
| MACD & Hist | 14d | +0.021 [-0.042, +0.093] (noise) | +0.023 [-0.002, +0.046] (noise) | +1.12 [+0.05, +2.28] (positive) |
| MACD & Hist | 30d | +0.033 [-0.018, +0.098] (noise) | +0.012 [-0.013, +0.037] (noise) | +1.05 [-1.38, +3.45] (noise) |
| Ichimoku Cloud | 1d | +0.010 [-0.013, +0.030] (noise) | -0.003 [-0.014, +0.008] (noise) | +0.10 [+0.01, +0.21] (positive) |
| Ichimoku Cloud | 3d | +0.013 [-0.026, +0.049] (noise) | +0.008 [-0.010, +0.025] (noise) | +0.26 [-0.03, +0.52] (noise) |
| Ichimoku Cloud | 7d | +0.015 [-0.041, +0.063] (noise) | +0.017 [-0.007, +0.042] (noise) | +0.68 [+0.04, +1.42] (positive) |
| Ichimoku Cloud | 14d | +0.015 [-0.062, +0.090] (noise) | +0.020 [-0.012, +0.050] (noise) | +1.42 [+0.20, +2.64] (positive) |
| Ichimoku Cloud | 30d | +0.004 [-0.082, +0.103] (noise) | +0.020 [-0.016, +0.055] (noise) | +2.64 [-0.63, +6.53] (noise) |
| Bollinger Bands | 1d | -0.009 [-0.033, +0.013] (noise) | +0.007 [-0.004, +0.016] (noise) | -0.05 [-0.15, +0.06] (noise) |
| Bollinger Bands | 3d | -0.008 [-0.047, +0.025] (noise) | +0.003 [-0.011, +0.015] (noise) | -0.28 [-0.55, -0.02] (negative) |
| Bollinger Bands | 7d | +0.001 [-0.045, +0.046] (noise) | -0.005 [-0.021, +0.012] (noise) | -0.53 [-1.17, +0.09] (noise) |
| Bollinger Bands | 14d | -0.017 [-0.081, +0.040] (noise) | -0.011 [-0.034, +0.011] (noise) | -0.84 [-2.09, +0.30] (noise) |
| Bollinger Bands | 30d | -0.029 [-0.090, +0.017] (noise) | -0.003 [-0.031, +0.023] (noise) | -1.12 [-3.87, +1.30] (noise) |
| Volume | 1d | -0.000 [-0.018, +0.017] (noise) | -0.012 [-0.025, -0.000] (negative) | +0.08 [-0.03, +0.18] (noise) |
| Volume | 3d | +0.005 [-0.011, +0.020] (noise) | -0.012 [-0.021, -0.001] (negative) | +0.12 [-0.14, +0.42] (noise) |
| Volume | 7d | +0.005 [-0.013, +0.022] (noise) | -0.007 [-0.017, +0.005] (noise) | +0.01 [-0.61, +0.66] (noise) |
| Volume | 14d | +0.008 [-0.012, +0.027] (noise) | -0.005 [-0.017, +0.006] (noise) | -0.11 [-1.40, +1.15] (noise) |
| Volume | 30d | +0.021 [+0.007, +0.037] (positive) | -0.000 [-0.011, +0.010] (noise) | +0.24 [-2.93, +3.44] (noise) |
| OBV | 1d | +0.008 [-0.008, +0.025] (noise) | -0.005 [-0.017, +0.005] (noise) | +0.09 [-0.00, +0.19] (noise) |
| OBV | 3d | +0.002 [-0.026, +0.033] (noise) | +0.000 [-0.015, +0.015] (noise) | +0.15 [-0.13, +0.41] (noise) |
| OBV | 7d | -0.012 [-0.052, +0.026] (noise) | +0.001 [-0.018, +0.020] (noise) | +0.12 [-0.46, +0.73] (noise) |
| OBV | 14d | -0.006 [-0.055, +0.048] (noise) | +0.006 [-0.015, +0.028] (noise) | +0.25 [-0.90, +1.43] (noise) |
| OBV | 30d | +0.005 [-0.040, +0.058] (noise) | -0.006 [-0.031, +0.024] (noise) | +0.27 [-2.39, +3.10] (noise) |
| Performance | 1d | -0.002 [-0.025, +0.025] (noise) | -0.013 [-0.023, -0.001] (negative) | +0.16 [+0.08, +0.26] (positive) |
| Performance | 3d | -0.007 [-0.048, +0.036] (noise) | -0.013 [-0.027, +0.003] (noise) | +0.37 [+0.13, +0.64] (positive) |
| Performance | 7d | -0.011 [-0.057, +0.038] (noise) | -0.009 [-0.030, +0.011] (noise) | +0.56 [+0.03, +1.15] (positive) |
| Performance | 14d | +0.015 [-0.041, +0.074] (noise) | +0.010 [-0.011, +0.031] (noise) | +1.01 [+0.13, +2.03] (positive) |
| Performance | 30d | +0.032 [-0.012, +0.087] (noise) | +0.009 [-0.014, +0.031] (noise) | +1.27 [-0.21, +3.21] (noise) |

## 3. Extremes

Average forward return on those days minus the asset's own average, % [95% band], and how many days.

### stock

| Rule | 1d | 3d | 7d | 14d | 30d |
| --- | --- | --- | --- | --- | --- |
| top 10% of own scores | +0.00 [-0.05, +0.05] n=11265 | -0.00 [-0.17, +0.14] n=11248 | -0.06 [-0.41, +0.26] n=11223 | -0.21 [-0.85, +0.34] n=11171 | -0.55 [-1.90, +0.54] n=11046 |
| bottom 10% of own scores | +0.04 [-0.14, +0.19] n=11246 | +0.07 [-0.50, +0.49] n=11240 | +0.17 [-0.84, +0.94] n=11232 | +0.76 [-0.38, +1.96] n=11213 | +1.43 [-0.34, +3.00] n=11188 |
| score 80 or more | -0.03 [-0.13, +0.08] n=2001 | -0.02 [-0.29, +0.22] n=1998 | -0.07 [-0.52, +0.38] n=1995 | -0.34 [-1.20, +0.42] n=1989 | -0.85 [-2.61, +0.53] n=1968 |
| score 20 or less | +0.04 [-0.20, +0.28] n=1652 | +0.11 [-0.62, +0.72] n=1652 | +0.49 [-0.96, +1.52] n=1652 | +1.26 [-0.35, +2.82] n=1650 | +1.41 [-1.11, +3.72] n=1647 |
| score 70 or more | -0.02 [-0.06, +0.02] n=27375 | -0.04 [-0.18, +0.08] n=27346 | -0.12 [-0.42, +0.15] n=27267 | -0.28 [-0.87, +0.21] n=27137 | -0.70 [-1.96, +0.35] n=26808 |
| score 30 or less | +0.04 [-0.13, +0.18] n=14713 | +0.08 [-0.42, +0.46] n=14706 | +0.14 [-0.87, +0.89] n=14695 | +0.61 [-0.54, +1.78] n=14672 | +1.27 [-0.53, +2.83] n=14634 |
| trend up, stretched down (pullback) | +1.61 [+1.61, +1.61] n=1 | +1.05 [+1.05, +1.05] n=1 | -3.29 [-3.29, -3.29] n=1 | -8.92 [-8.92, -8.92] n=1 | -7.28 [-7.28, -7.28] n=1 |
| trend down, stretched up (bounce) | -1.61 [-1.61, -1.61] n=1 | -4.83 [-4.83, -4.83] n=1 | -1.48 [-1.48, -1.48] n=1 | +1.85 [+1.85, +1.85] n=1 | +5.78 [+5.78, +5.78] n=1 |

### crypto

| Rule | 1d | 3d | 7d | 14d | 30d |
| --- | --- | --- | --- | --- | --- |
| top 10% of own scores | +0.18 [-0.18, +0.49] n=5834 | +0.52 [-0.43, +1.37] n=5831 | +1.07 [-1.10, +3.07] n=5822 | +1.86 [-2.47, +6.32] n=5811 | +1.38 [-8.01, +12.26] n=5806 |
| bottom 10% of own scores | -0.13 [-0.40, +0.12] n=5625 | -0.32 [-1.08, +0.46] n=5613 | -0.75 [-2.43, +1.05] n=5600 | -1.35 [-4.57, +1.84] n=5594 | -6.73 [-11.86, -1.09] n=5547 |
| score 80 or more | +0.08 [-0.30, +0.50] n=1878 | -0.35 [-1.35, +0.73] n=1877 | +0.06 [-2.72, +2.87] n=1876 | +0.66 [-4.19, +5.76] n=1873 | -0.34 [-11.79, +13.33] n=1872 |
| score 20 or less | +0.03 [-0.38, +0.45] n=1648 | -0.55 [-1.50, +0.35] n=1646 | -0.60 [-2.77, +1.55] n=1639 | -0.11 [-3.68, +3.58] n=1639 | -5.40 [-11.41, +0.90] n=1627 |
| score 70 or more | +0.29 [-0.04, +0.57] n=10983 | +0.70 [-0.19, +1.56] n=10975 | +1.21 [-0.77, +3.14] n=10951 | +1.51 [-2.37, +5.21] n=10920 | +0.93 [-7.89, +10.82] n=10890 |
| score 30 or less | -0.18 [-0.41, +0.05] n=12568 | -0.45 [-1.09, +0.23] n=12543 | -1.01 [-2.51, +0.48] n=12520 | -1.99 [-4.83, +0.89] n=12509 | -5.27 [-10.23, +0.18] n=12386 |
| trend up, stretched down (pullback) | -11.25 [-12.10, -10.10] n=4 | -15.20 [-23.45, -3.86] n=4 | +5.87 [-11.29, +11.59] n=4 | -7.41 [-11.67, -4.82] n=4 | -10.10 [-12.74, -8.91] n=4 |
| trend down, stretched up (bounce) | +0.70 [+0.70, +0.70] n=1 | -0.57 [-0.57, -0.57] n=1 | -3.97 [-3.97, -3.97] n=1 | +3.98 [+3.98, +3.98] n=1 | -9.86 [-9.86, -9.86] n=1 |

## 4. Regimes

Pooled time-series rank correlation inside each condition [95% band].

### stock

| Signal | Condition | 7d | 14d | 30d |
| --- | --- | --- | --- | --- |
| Trend | asset trending (ADX 25+) | -0.048 [-0.099, +0.006] | -0.059 [-0.114, -0.005] | -0.087 [-0.167, -0.014] |
| Trend | asset ranging (ADX under 20) | -0.033 [-0.063, -0.002] | -0.058 [-0.097, -0.019] | -0.077 [-0.114, -0.034] |
| Trend | benchmark above 200-day | -0.038 [-0.070, -0.011] | -0.048 [-0.081, -0.017] | -0.064 [-0.099, -0.024] |
| Trend | benchmark below 200-day | -0.049 [-0.126, +0.036] | -0.092 [-0.170, -0.010] | -0.179 [-0.295, -0.055] |
| Stretch | asset trending (ADX 25+) | +0.047 [-0.002, +0.096] | +0.054 [+0.007, +0.098] | +0.083 [+0.023, +0.149] |
| Stretch | asset ranging (ADX under 20) | +0.019 [-0.012, +0.049] | +0.040 [+0.005, +0.076] | +0.058 [+0.022, +0.093] |
| Stretch | benchmark above 200-day | +0.034 [+0.009, +0.067] | +0.046 [+0.011, +0.075] | +0.061 [+0.025, +0.098] |
| Stretch | benchmark below 200-day | +0.018 [-0.061, +0.091] | +0.041 [-0.042, +0.129] | +0.129 [+0.031, +0.226] |
| score | asset trending (ADX 25+) | -0.041 [-0.090, +0.012] | -0.055 [-0.109, -0.001] | -0.081 [-0.160, -0.008] |
| score | asset ranging (ADX under 20) | -0.036 [-0.063, -0.007] | -0.061 [-0.099, -0.027] | -0.079 [-0.116, -0.038] |
| score | benchmark above 200-day | -0.035 [-0.065, -0.010] | -0.047 [-0.077, -0.016] | -0.062 [-0.094, -0.024] |
| score | benchmark below 200-day | -0.057 [-0.129, +0.024] | -0.106 [-0.184, -0.026] | -0.180 [-0.296, -0.055] |

### crypto

| Signal | Condition | 7d | 14d | 30d |
| --- | --- | --- | --- | --- |
| Trend | asset trending (ADX 25+) | -0.024 [-0.092, +0.039] | -0.010 [-0.098, +0.076] | -0.012 [-0.117, +0.108] |
| Trend | asset ranging (ADX under 20) | +0.055 [-0.011, +0.124] | +0.057 [-0.030, +0.147] | +0.072 [-0.028, +0.171] |
| Trend | benchmark above 200-day | +0.033 [-0.029, +0.099] | +0.034 [-0.038, +0.105] | +0.018 [-0.066, +0.124] |
| Trend | benchmark below 200-day | -0.035 [-0.135, +0.058] | -0.025 [-0.153, +0.105] | -0.004 [-0.115, +0.128] |
| Stretch | asset trending (ADX 25+) | +0.023 [-0.042, +0.091] | +0.002 [-0.086, +0.083] | -0.001 [-0.096, +0.077] |
| Stretch | asset ranging (ADX under 20) | -0.060 [-0.131, +0.002] | -0.066 [-0.147, +0.016] | -0.076 [-0.164, +0.000] |
| Stretch | benchmark above 200-day | -0.023 [-0.092, +0.041] | -0.043 [-0.120, +0.024] | -0.032 [-0.123, +0.042] |
| Stretch | benchmark below 200-day | +0.018 [-0.067, +0.113] | +0.015 [-0.108, +0.131] | -0.007 [-0.132, +0.092] |
| score | asset trending (ADX 25+) | -0.018 [-0.083, +0.038] | -0.008 [-0.086, +0.069] | -0.012 [-0.119, +0.107] |
| score | asset ranging (ADX under 20) | +0.050 [-0.012, +0.118] | +0.045 [-0.039, +0.134] | +0.059 [-0.037, +0.156] |
| score | benchmark above 200-day | +0.033 [-0.027, +0.100] | +0.030 [-0.036, +0.099] | +0.013 [-0.072, +0.118] |
| score | benchmark below 200-day | -0.030 [-0.122, +0.055] | -0.023 [-0.142, +0.100] | +0.000 [-0.112, +0.122] |

## 5. Volatility (ATR%)

Mean partial rank correlation of ATR% with the size of later moves, after trailing volatility; and how many assets clear their own noise band.

- stock, 1d: mean +0.136, 61 of 61 assets clear the band
- stock, 7d: mean +0.269, 60 of 61 assets clear the band
- stock, 14d: mean +0.287, 56 of 61 assets clear the band
- crypto, 1d: mean +0.084, 24 of 25 assets clear the band
- crypto, 7d: mean +0.179, 23 of 25 assets clear the band
- crypto, 14d: mean +0.202, 19 of 25 assets clear the band

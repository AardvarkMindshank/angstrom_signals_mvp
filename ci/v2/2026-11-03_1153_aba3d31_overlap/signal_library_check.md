# Signal Library descriptive check (development data only, before 2024-10-30)

No forward returns. Agreement is measured on every 5th daily candle after a 260-candle warm-up.

## stock (61 assets, 122732 candles)

| Pair | both directional | agree when both directional |
|---|---|---|
| trend vs momentum | 0.398 | 0.844 |
| trend vs structure | 0.385 | 0.795 |
| momentum vs structure | 0.428 | 0.532 |

- Efficiency ratio vs ADX (Spearman, within asset): 0.46
- Efficiency ratio vs strength of the Trend reading: 0.578
- Zones kept per asset (median): 4.0; zone width median 1.308% of price

| Divergence | per 1,000 candles | share invalidated |
|---|---|---|
| rsi regular_bullish | 5.05 | 0.75 |
| rsi hidden_bullish | 7.83 | 0.813 |
| rsi regular_bearish | 9.48 | 0.967 |
| rsi hidden_bearish | 4.43 | 0.974 |
| macd regular_bullish | 8.07 | 0.782 |
| macd hidden_bullish | 12.37 | 0.805 |
| macd regular_bearish | 13.51 | 0.956 |
| macd hidden_bearish | 8.69 | 0.971 |

## crypto (25 assets, 60099 candles)

| Pair | both directional | agree when both directional |
|---|---|---|
| trend vs momentum | 0.365 | 0.807 |
| trend vs structure | 0.346 | 0.79 |
| momentum vs structure | 0.399 | 0.565 |

- Efficiency ratio vs ADX (Spearman, within asset): 0.435
- Efficiency ratio vs strength of the Trend reading: 0.543
- Zones kept per asset (median): 4.0; zone width median 1.969% of price

| Divergence | per 1,000 candles | share invalidated |
|---|---|---|
| rsi regular_bullish | 5.41 | 0.828 |
| rsi hidden_bullish | 7.39 | 0.869 |
| rsi regular_bearish | 5.44 | 0.865 |
| rsi hidden_bearish | 6.64 | 0.917 |
| macd regular_bullish | 10.92 | 0.86 |
| macd hidden_bullish | 12.48 | 0.865 |
| macd regular_bearish | 7.94 | 0.883 |
| macd hidden_bearish | 10.8 | 0.909 |

## Calculation time (ms, one year of daily candles)

- stock: pivots: 6.12
- stock: divergences (RSI): 7.94
- stock: structure breaks: 6.62
- stock: zones: 7.51
- crypto: pivots: 6.0
- crypto: divergences (RSI): 8.02
- crypto: structure breaks: 6.53
- crypto: zones: 7.21

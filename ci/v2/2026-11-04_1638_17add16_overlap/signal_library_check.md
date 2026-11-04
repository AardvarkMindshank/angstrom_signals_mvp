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
- Zones kept per asset (median): 4.0; zone width median 1.253% of price

| Divergence | per 1,000 candles | invalidated within 30 candles | expired untouched |
|---|---|---|---|
| rsi regular_bullish | 5.05 | 0.453 | 0.544 |
| rsi hidden_bullish | 7.83 | 0.467 | 0.524 |
| rsi regular_bearish | 9.48 | 0.631 | 0.36 |
| rsi hidden_bearish | 4.43 | 0.671 | 0.325 |
| macd regular_bullish | 8.07 | 0.452 | 0.538 |
| macd hidden_bullish | 12.37 | 0.489 | 0.499 |
| macd regular_bearish | 13.51 | 0.619 | 0.366 |
| macd hidden_bearish | 8.69 | 0.653 | 0.342 |

## crypto (25 assets, 60099 candles)

| Pair | both directional | agree when both directional |
|---|---|---|
| trend vs momentum | 0.365 | 0.807 |
| trend vs structure | 0.346 | 0.79 |
| momentum vs structure | 0.399 | 0.565 |

- Efficiency ratio vs ADX (Spearman, within asset): 0.435
- Efficiency ratio vs strength of the Trend reading: 0.543
- Zones kept per asset (median): 4.0; zone width median 2.043% of price

| Divergence | per 1,000 candles | invalidated within 30 candles | expired untouched |
|---|---|---|---|
| rsi regular_bullish | 5.41 | 0.48 | 0.52 |
| rsi hidden_bullish | 7.39 | 0.568 | 0.412 |
| rsi regular_bearish | 5.44 | 0.462 | 0.535 |
| rsi hidden_bearish | 6.64 | 0.519 | 0.479 |
| macd regular_bullish | 10.92 | 0.505 | 0.489 |
| macd hidden_bullish | 12.48 | 0.553 | 0.425 |
| macd regular_bearish | 7.94 | 0.514 | 0.474 |
| macd hidden_bearish | 10.8 | 0.53 | 0.467 |

## Calculation time (ms, one year of daily candles)

- stock: pivots: 6.25
- stock: divergences (RSI): 8.05
- stock: structure breaks: 6.77
- stock: zones: 7.79
- crypto: pivots: 6.09
- crypto: divergences (RSI): 8.0
- crypto: structure breaks: 6.62
- crypto: zones: 7.39

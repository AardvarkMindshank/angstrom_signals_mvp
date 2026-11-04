# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 5.19 | 0.173 | 38.4 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.09 | 0.07 | 2.0 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 54.29 | 0.149 | 15.4 | 21.2 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.91 | 0.049 | 1.3 | 42.0 |
| dev-BTC-USD | 30 | exact | 2.98 | 0.099 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 1.97 | 0.066 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 36.93 | 0.101 | 0.8 | 19.7 |
| dev-BTC-USD | 365 | slice shortcut | 24.05 | 0.066 | 0.0 | 21.3 |
| dev-AAPL | 30 | exact | 2.86 | 0.095 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 1.86 | 0.062 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 34.49 | 0.094 | 0.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 21.78 | 0.06 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 36.06 | 1.202 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 108.19 | 1.202 | 10.0 | 0.0 | {'partial': 90} |

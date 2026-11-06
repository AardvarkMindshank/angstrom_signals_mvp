# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.51 | 0.217 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.76 | 0.092 | 8.8 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 68.33 | 0.187 | 7.6 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.87 | 0.068 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.04 | 0.135 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.79 | 0.093 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 51.22 | 0.14 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.29 | 0.094 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 4.11 | 0.137 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.68 | 0.089 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.91 | 0.131 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.51 | 0.086 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.64 | 1.455 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.21 | 1.458 | 10.0 | 0.0 | {'partial': 90} |

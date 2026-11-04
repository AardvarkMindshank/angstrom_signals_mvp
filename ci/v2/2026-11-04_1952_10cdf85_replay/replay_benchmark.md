# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.53 | 0.218 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.8 | 0.093 | 1.3 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 71.24 | 0.195 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.81 | 0.068 | 2.6 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.9 | 0.13 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.68 | 0.089 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 48.76 | 0.134 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.51 | 0.092 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.87 | 0.129 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.63 | 0.088 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.24 | 0.127 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 32.39 | 0.089 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.98 | 1.466 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 132.66 | 1.474 | 10.0 | 0.0 | {'partial': 90} |

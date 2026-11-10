# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.66 | 0.155 | 41.4 | 7.1 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.07 | 0.069 | 7.2 | 24.7 |
| synthetic-crypto-s11 | 365 | exact | 47.65 | 0.131 | 11.3 | 18.0 |
| synthetic-crypto-s11 | 365 | slice shortcut | 18.57 | 0.051 | 0.8 | 38.5 |
| dev-BTC-USD | 30 | exact | 2.85 | 0.095 | 0.0 | 3.5 |
| dev-BTC-USD | 30 | slice shortcut | 2.03 | 0.068 | 0.0 | 4.5 |
| dev-BTC-USD | 365 | exact | 36.29 | 0.099 | 1.1 | 15.9 |
| dev-BTC-USD | 365 | slice shortcut | 24.83 | 0.068 | 0.0 | 17.2 |
| dev-AAPL | 30 | exact | 2.77 | 0.092 | 0.0 | 4.2 |
| dev-AAPL | 30 | slice shortcut | 1.95 | 0.065 | 0.0 | 5.0 |
| dev-AAPL | 365 | exact | 34.26 | 0.094 | 0.0 | 14.6 |
| dev-AAPL | 365 | slice shortcut | 23.17 | 0.063 | 0.0 | 16.8 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.24 | 1.075 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 96.17 | 1.069 | 10.0 | 0.0 | {'partial': 90} |

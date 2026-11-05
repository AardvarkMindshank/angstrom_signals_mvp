# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.39 | 0.146 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.92 | 0.064 | 1.2 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 45.93 | 0.126 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.0 | 0.047 | 1.7 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.72 | 0.091 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.9 | 0.063 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 33.9 | 0.093 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 23.21 | 0.064 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.65 | 0.088 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.81 | 0.06 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 32.08 | 0.088 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.46 | 0.059 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.14 | 1.038 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 93.66 | 1.041 | 10.1 | 0.0 | {'partial': 90} |

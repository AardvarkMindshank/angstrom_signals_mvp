# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.65 | 0.222 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.79 | 0.093 | 7.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 69.99 | 0.192 | 8.4 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.93 | 0.068 | 2.4 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.04 | 0.135 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.76 | 0.092 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 50.43 | 0.138 | 1.0 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.88 | 0.093 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.97 | 0.132 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.69 | 0.09 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 48.38 | 0.133 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.52 | 0.086 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.76 | 1.459 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.32 | 1.459 | 10.1 | 0.0 | {'partial': 90} |

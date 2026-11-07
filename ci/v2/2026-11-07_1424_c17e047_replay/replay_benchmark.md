# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.44 | 0.148 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.94 | 0.065 | 4.2 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 46.4 | 0.127 | 12.1 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.24 | 0.047 | 14.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.75 | 0.092 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.91 | 0.064 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 34.26 | 0.094 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 23.54 | 0.064 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.67 | 0.089 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.84 | 0.061 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 32.4 | 0.089 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.74 | 0.06 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.41 | 1.047 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 94.68 | 1.052 | 10.0 | 0.0 | {'partial': 90} |

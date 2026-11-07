# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.46 | 0.149 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.97 | 0.066 | 1.8 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 46.0 | 0.126 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.17 | 0.047 | 2.4 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.76 | 0.092 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.92 | 0.064 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 34.09 | 0.093 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 23.53 | 0.064 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.67 | 0.089 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.84 | 0.061 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 32.38 | 0.089 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.72 | 0.06 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.5 | 1.05 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 94.82 | 1.054 | 10.0 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.41 | 0.147 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.92 | 0.064 | 8.9 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 45.84 | 0.126 | 3.7 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 16.92 | 0.046 | 2.5 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.71 | 0.09 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.88 | 0.063 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 33.83 | 0.093 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 23.32 | 0.064 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.68 | 0.089 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.81 | 0.06 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 32.16 | 0.088 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.77 | 0.06 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.66 | 1.055 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 95.04 | 1.056 | 10.0 | 0.0 | {'partial': 90} |

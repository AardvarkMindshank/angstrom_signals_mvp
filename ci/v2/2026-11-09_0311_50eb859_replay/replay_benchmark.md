# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.41 | 0.214 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.74 | 0.091 | 8.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 66.89 | 0.183 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.16 | 0.066 | 1.9 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.9 | 0.13 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.68 | 0.089 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 48.43 | 0.133 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 32.85 | 0.09 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.81 | 0.127 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.6 | 0.087 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.7 | 0.128 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 32.28 | 0.088 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.95 | 1.465 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.4 | 1.46 | 10.0 | 0.0 | {'partial': 90} |

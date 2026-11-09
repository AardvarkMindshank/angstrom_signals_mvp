# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.55 | 0.218 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.8 | 0.093 | 1.7 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 68.42 | 0.187 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.33 | 0.069 | 1.6 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.05 | 0.135 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.76 | 0.092 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 50.36 | 0.138 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.85 | 0.093 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.93 | 0.131 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.66 | 0.089 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.57 | 0.13 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.62 | 0.087 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.89 | 1.463 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.02 | 1.456 | 10.1 | 0.0 | {'partial': 90} |

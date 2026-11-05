# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.31 | 0.21 | 41.2 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.81 | 0.094 | 8.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 66.18 | 0.181 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.18 | 0.069 | 2.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.95 | 0.132 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.78 | 0.093 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 50.33 | 0.138 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.08 | 0.093 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 4.01 | 0.134 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.72 | 0.091 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.81 | 0.131 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.71 | 0.087 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.09 | 1.436 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 128.97 | 1.433 | 10.1 | 0.0 | {'partial': 90} |

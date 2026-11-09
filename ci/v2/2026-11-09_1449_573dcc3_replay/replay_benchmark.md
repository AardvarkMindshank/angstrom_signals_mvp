# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.38 | 0.213 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.77 | 0.092 | 8.6 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 66.51 | 0.182 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.88 | 0.068 | 2.0 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.96 | 0.132 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.72 | 0.091 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 49.09 | 0.134 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.51 | 0.092 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.82 | 0.127 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.6 | 0.087 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.54 | 0.128 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 30.78 | 0.084 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.72 | 1.457 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 130.95 | 1.455 | 10.1 | 0.0 | {'partial': 90} |

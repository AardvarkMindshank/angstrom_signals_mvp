# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.37 | 0.212 | 41.4 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.74 | 0.091 | 2.0 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 66.33 | 0.182 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.65 | 0.068 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.97 | 0.132 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.75 | 0.092 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 49.53 | 0.136 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.53 | 0.092 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.88 | 0.129 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.64 | 0.088 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.77 | 0.128 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.18 | 0.085 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.35 | 1.445 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 129.74 | 1.442 | 10.0 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.94 | 0.131 | 40.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.59 | 0.053 | 8.3 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 41.66 | 0.114 | 12.1 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 14.44 | 0.04 | 1.9 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.34 | 0.078 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.55 | 0.052 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 29.16 | 0.08 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 18.9 | 0.052 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.26 | 0.075 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.46 | 0.049 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 27.15 | 0.074 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 17.31 | 0.047 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 28.7 | 0.957 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 86.22 | 0.958 | 10.1 | 0.0 | {'partial': 90} |

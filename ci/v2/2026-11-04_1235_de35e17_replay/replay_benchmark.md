# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.35 | 0.145 | 41.7 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.28 | 0.076 | 8.2 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 44.3 | 0.121 | 15.8 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 22.19 | 0.061 | 2.2 | 42.3 |
| dev-BTC-USD | 30 | exact | 2.75 | 0.092 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.33 | 0.078 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 33.57 | 0.092 | 0.7 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 29.33 | 0.08 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 2.7 | 0.09 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.31 | 0.077 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 32.83 | 0.09 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 27.52 | 0.075 | 0.0 | 20.0 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.87 | 1.096 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 98.86 | 1.098 | 10.0 | 0.0 | {'partial': 90} |

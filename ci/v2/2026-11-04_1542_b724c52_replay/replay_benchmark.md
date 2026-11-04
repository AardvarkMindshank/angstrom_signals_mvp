# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.14 | 0.205 | 41.5 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.57 | 0.086 | 8.6 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 63.51 | 0.174 | 15.5 | 21.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 22.22 | 0.061 | 15.7 | 42.0 |
| dev-BTC-USD | 30 | exact | 3.71 | 0.124 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.52 | 0.084 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 46.16 | 0.126 | 1.0 | 19.6 |
| dev-BTC-USD | 365 | slice shortcut | 30.99 | 0.085 | 0.0 | 21.4 |
| dev-AAPL | 30 | exact | 3.63 | 0.121 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.44 | 0.081 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 43.6 | 0.119 | 0.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 28.32 | 0.078 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 42.91 | 1.43 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 128.79 | 1.431 | 10.0 | -1.0 | {'partial': 90} |

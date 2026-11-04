# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.27 | 0.109 | 39.0 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.37 | 0.046 | 1.9 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 33.58 | 0.092 | 15.4 | 21.2 |
| synthetic-crypto-s11 | 365 | slice shortcut | 11.41 | 0.031 | 13.7 | 42.0 |
| dev-BTC-USD | 30 | exact | 1.85 | 0.062 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 1.28 | 0.043 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 22.85 | 0.063 | 1.0 | 19.7 |
| dev-BTC-USD | 365 | slice shortcut | 16.82 | 0.046 | 0.0 | 21.4 |
| dev-AAPL | 30 | exact | 1.79 | 0.06 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 1.23 | 0.041 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 22.05 | 0.06 | -1.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 14.15 | 0.039 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 24.47 | 0.816 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 72.94 | 0.81 | 10.0 | 0.0 | {'partial': 90} |

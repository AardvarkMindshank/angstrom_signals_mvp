# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.31 | 0.11 | 38.6 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.39 | 0.046 | 1.9 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 33.2 | 0.091 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.75 | 0.035 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.06 | 0.069 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.39 | 0.046 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 25.48 | 0.07 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.07 | 0.047 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.85 | 0.062 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.23 | 0.041 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 22.28 | 0.061 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.75 | 0.043 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 24.18 | 0.806 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 70.66 | 0.785 | 10.1 | 0.0 | {'partial': 90} |

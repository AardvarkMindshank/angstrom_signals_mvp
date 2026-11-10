# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.37 | 0.212 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.8 | 0.093 | 7.3 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 65.93 | 0.181 | 12.1 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.37 | 0.07 | 2.0 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.95 | 0.132 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.71 | 0.09 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 49.74 | 0.136 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.69 | 0.095 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.92 | 0.131 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.72 | 0.091 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 48.48 | 0.133 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 32.21 | 0.088 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.89 | 1.463 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.09 | 1.457 | 10.1 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.44 | 0.215 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.71 | 0.09 | 1.6 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 66.03 | 0.181 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 23.82 | 0.065 | 1.9 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.88 | 0.129 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.64 | 0.088 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 47.87 | 0.131 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 33.25 | 0.091 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.93 | 0.131 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.64 | 0.088 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.93 | 0.129 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 30.79 | 0.084 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.49 | 1.45 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 129.94 | 1.444 | 10.0 | 0.0 | {'partial': 90} |

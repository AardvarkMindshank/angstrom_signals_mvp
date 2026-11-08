# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.53 | 0.218 | 41.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.81 | 0.094 | -0.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 68.53 | 0.188 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.63 | 0.07 | 2.5 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.18 | 0.139 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.88 | 0.096 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 52.18 | 0.143 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.1 | 0.093 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.97 | 0.132 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.71 | 0.09 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.9 | 0.131 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.76 | 0.087 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.39 | 1.446 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 130.73 | 1.453 | 10.0 | 0.0 | {'partial': 90} |

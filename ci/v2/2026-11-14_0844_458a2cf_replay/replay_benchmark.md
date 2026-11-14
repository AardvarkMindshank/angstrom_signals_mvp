# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 10.27 | 0.342 | 40.2 | 7.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 6.69 | 0.223 | 7.9 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 110.23 | 0.302 | 10.7 | 18.2 |
| synthetic-crypto-s11 | 365 | slice shortcut | 67.4 | 0.185 | 8.8 | 39.8 |
| dev-BTC-USD | 30 | exact | 4.11 | 0.137 | 0.0 | 4.0 |
| dev-BTC-USD | 30 | slice shortcut | 3.06 | 0.102 | 0.0 | 5.0 |
| dev-BTC-USD | 365 | exact | 51.48 | 0.141 | 0.4 | 15.2 |
| dev-BTC-USD | 365 | slice shortcut | 37.62 | 0.103 | 0.0 | 16.7 |
| dev-AAPL | 30 | exact | 3.97 | 0.132 | 0.0 | 4.7 |
| dev-AAPL | 30 | slice shortcut | 2.96 | 0.099 | 0.0 | 5.4 |
| dev-AAPL | 365 | exact | 48.82 | 0.134 | 0.0 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 35.15 | 0.096 | 0.0 | 16.3 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 35.75 | 1.192 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 107.2 | 1.191 | 10.0 | 0.0 | {'partial': 90} |

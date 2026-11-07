# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.97 | 0.232 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.99 | 0.1 | 7.1 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 75.04 | 0.206 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 26.37 | 0.072 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.25 | 0.142 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.82 | 0.094 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 53.12 | 0.146 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.8 | 0.095 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 4.14 | 0.138 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.74 | 0.091 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 49.57 | 0.136 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 32.7 | 0.09 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 45.27 | 1.509 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 138.88 | 1.543 | 10.0 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 9.12 | 0.304 | 43.6 | 8.0 |
| synthetic-crypto-s11 | 30 | slice shortcut | 6.18 | 0.206 | 7.7 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 97.23 | 0.266 | 10.6 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 62.67 | 0.172 | 18.5 | 39.9 |
| dev-BTC-USD | 30 | exact | 3.7 | 0.123 | 0.0 | 4.1 |
| dev-BTC-USD | 30 | slice shortcut | 2.85 | 0.095 | 0.0 | 5.1 |
| dev-BTC-USD | 365 | exact | 45.94 | 0.126 | 0.5 | 15.3 |
| dev-BTC-USD | 365 | slice shortcut | 35.13 | 0.096 | 0.0 | 16.6 |
| dev-AAPL | 30 | exact | 3.59 | 0.12 | 0.0 | 4.8 |
| dev-AAPL | 30 | slice shortcut | 2.73 | 0.091 | 0.0 | 5.5 |
| dev-AAPL | 365 | exact | 43.76 | 0.12 | 0.0 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 32.87 | 0.09 | 0.0 | 16.2 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.41 | 1.047 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 94.44 | 1.049 | 10.0 | 0.0 | {'partial': 90} |

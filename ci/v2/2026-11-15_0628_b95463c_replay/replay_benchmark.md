# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 9.5 | 0.317 | 42.5 | 8.0 |
| synthetic-crypto-s11 | 30 | slice shortcut | 6.45 | 0.215 | 8.0 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 102.53 | 0.281 | 10.5 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 64.33 | 0.176 | 8.4 | 39.9 |
| dev-BTC-USD | 30 | exact | 3.96 | 0.132 | 0.0 | 4.1 |
| dev-BTC-USD | 30 | slice shortcut | 2.97 | 0.099 | 0.0 | 5.1 |
| dev-BTC-USD | 365 | exact | 48.75 | 0.134 | 0.5 | 15.3 |
| dev-BTC-USD | 365 | slice shortcut | 35.9 | 0.098 | 0.0 | 16.6 |
| dev-AAPL | 30 | exact | 3.72 | 0.124 | 0.0 | 4.8 |
| dev-AAPL | 30 | slice shortcut | 2.88 | 0.096 | 0.0 | 5.5 |
| dev-AAPL | 365 | exact | 46.07 | 0.126 | 0.0 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 34.72 | 0.095 | 0.0 | 16.2 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.9 | 1.097 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 97.54 | 1.084 | 10.0 | 0.0 | {'partial': 90} |

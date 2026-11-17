# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 9.69 | 0.323 | 43.0 | 8.0 |
| synthetic-crypto-s11 | 30 | slice shortcut | 6.39 | 0.213 | 8.2 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 102.23 | 0.28 | 10.6 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 64.43 | 0.177 | 4.7 | 39.9 |
| dev-BTC-USD | 30 | exact | 3.96 | 0.132 | 0.0 | 4.1 |
| dev-BTC-USD | 30 | slice shortcut | 2.98 | 0.099 | 0.0 | 5.1 |
| dev-BTC-USD | 365 | exact | 47.85 | 0.131 | 0.5 | 15.3 |
| dev-BTC-USD | 365 | slice shortcut | 35.64 | 0.098 | 0.0 | 16.6 |
| dev-AAPL | 30 | exact | 3.8 | 0.127 | 0.0 | 4.8 |
| dev-AAPL | 30 | slice shortcut | 2.89 | 0.096 | 0.0 | 5.5 |
| dev-AAPL | 365 | exact | 45.23 | 0.124 | 0.0 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 33.86 | 0.093 | 0.0 | 16.2 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.22 | 1.074 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 95.82 | 1.065 | 10.0 | 0.0 | {'partial': 90} |

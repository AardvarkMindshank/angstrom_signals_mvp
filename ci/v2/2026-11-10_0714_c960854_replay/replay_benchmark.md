# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.46 | 0.215 | 41.3 | 7.1 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.92 | 0.097 | 8.5 | 24.7 |
| synthetic-crypto-s11 | 365 | exact | 67.5 | 0.185 | 6.8 | 18.0 |
| synthetic-crypto-s11 | 365 | slice shortcut | 26.55 | 0.073 | 1.8 | 38.5 |
| dev-BTC-USD | 30 | exact | 4.09 | 0.136 | 0.0 | 3.5 |
| dev-BTC-USD | 30 | slice shortcut | 2.83 | 0.094 | 0.0 | 4.5 |
| dev-BTC-USD | 365 | exact | 50.67 | 0.139 | 1.0 | 15.9 |
| dev-BTC-USD | 365 | slice shortcut | 35.0 | 0.096 | 0.0 | 17.2 |
| dev-AAPL | 30 | exact | 3.99 | 0.133 | 0.0 | 4.2 |
| dev-AAPL | 30 | slice shortcut | 2.77 | 0.092 | 0.0 | 5.0 |
| dev-AAPL | 365 | exact | 48.33 | 0.132 | 0.0 | 14.6 |
| dev-AAPL | 365 | slice shortcut | 33.65 | 0.092 | 0.0 | 16.8 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.17 | 1.439 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 129.17 | 1.435 | 10.1 | 0.0 | {'partial': 90} |

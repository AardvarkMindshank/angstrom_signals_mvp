# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.91 | 0.23 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.89 | 0.096 | 8.7 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 70.82 | 0.194 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.99 | 0.071 | 2.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.28 | 0.143 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.88 | 0.096 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 52.82 | 0.145 | 1.0 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 35.4 | 0.097 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 4.08 | 0.136 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.75 | 0.092 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 50.16 | 0.137 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 32.14 | 0.088 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 44.78 | 1.493 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 134.63 | 1.496 | 10.0 | 0.0 | {'partial': 90} |

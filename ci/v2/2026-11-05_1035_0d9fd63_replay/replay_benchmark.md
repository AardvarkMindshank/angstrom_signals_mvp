# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.48 | 0.216 | 41.4 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.88 | 0.096 | 3.6 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 69.41 | 0.19 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 25.24 | 0.069 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.1 | 0.137 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.81 | 0.094 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 51.07 | 0.14 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.9 | 0.096 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.98 | 0.133 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.7 | 0.09 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.57 | 0.13 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.98 | 0.088 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 44.05 | 1.468 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.05 | 1.456 | 10.1 | 0.0 | {'partial': 90} |

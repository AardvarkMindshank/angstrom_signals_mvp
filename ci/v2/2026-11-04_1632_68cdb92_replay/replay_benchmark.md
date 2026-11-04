# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.48 | 0.216 | 40.7 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.63 | 0.088 | 1.4 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 65.96 | 0.181 | 15.5 | 21.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 23.11 | 0.063 | 15.1 | 42.0 |
| dev-BTC-USD | 30 | exact | 4.04 | 0.135 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.68 | 0.089 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 49.96 | 0.137 | 1.2 | 19.6 |
| dev-BTC-USD | 365 | slice shortcut | 31.98 | 0.088 | 0.0 | 21.4 |
| dev-AAPL | 30 | exact | 3.82 | 0.127 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.5 | 0.083 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 45.43 | 0.124 | 0.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 28.86 | 0.079 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.56 | 1.452 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 130.33 | 1.448 | 10.0 | 0.0 | {'partial': 90} |

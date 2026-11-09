# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.68 | 0.223 | 42.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.89 | 0.096 | 1.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 70.62 | 0.193 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 26.21 | 0.072 | 15.6 | 39.2 |
| dev-BTC-USD | 30 | exact | 4.11 | 0.137 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.78 | 0.093 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 51.67 | 0.142 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 34.39 | 0.094 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.92 | 0.131 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.66 | 0.089 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 47.03 | 0.129 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 31.41 | 0.086 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.89 | 1.463 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.84 | 1.465 | 10.1 | 0.0 | {'partial': 90} |

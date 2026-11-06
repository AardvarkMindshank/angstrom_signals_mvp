# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.18 | 0.106 | 39.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.4 | 0.047 | 8.7 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 33.8 | 0.093 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 11.9 | 0.033 | 1.9 | 39.2 |
| dev-BTC-USD | 30 | exact | 1.89 | 0.063 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.32 | 0.044 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 24.48 | 0.067 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 16.58 | 0.045 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.85 | 0.062 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.29 | 0.043 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 22.79 | 0.062 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 14.87 | 0.041 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 23.3 | 0.777 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 76.65 | 0.852 | 10.0 | 0.0 | {'partial': 90} |

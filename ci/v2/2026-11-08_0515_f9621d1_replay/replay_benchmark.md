# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.4 | 0.113 | 38.7 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.44 | 0.048 | 7.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 35.76 | 0.098 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 13.29 | 0.036 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.07 | 0.069 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.42 | 0.047 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 25.82 | 0.071 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.21 | 0.047 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.87 | 0.062 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.29 | 0.043 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 23.3 | 0.064 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.46 | 0.042 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 25.31 | 0.844 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 77.02 | 0.856 | 10.0 | 0.0 | {'partial': 90} |

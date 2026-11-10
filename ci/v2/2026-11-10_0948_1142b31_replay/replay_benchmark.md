# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.61 | 0.22 | 42.1 | 7.1 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.95 | 0.098 | 1.7 | 24.7 |
| synthetic-crypto-s11 | 365 | exact | 71.05 | 0.195 | 11.3 | 17.9 |
| synthetic-crypto-s11 | 365 | slice shortcut | 27.16 | 0.074 | 0.3 | 38.6 |
| dev-BTC-USD | 30 | exact | 4.26 | 0.142 | 0.0 | 3.5 |
| dev-BTC-USD | 30 | slice shortcut | 2.95 | 0.098 | 0.0 | 4.5 |
| dev-BTC-USD | 365 | exact | 53.16 | 0.146 | 1.0 | 15.9 |
| dev-BTC-USD | 365 | slice shortcut | 36.76 | 0.101 | 0.0 | 17.2 |
| dev-AAPL | 30 | exact | 4.25 | 0.142 | 0.0 | 4.2 |
| dev-AAPL | 30 | slice shortcut | 2.94 | 0.098 | 0.0 | 5.0 |
| dev-AAPL | 365 | exact | 51.46 | 0.141 | 0.0 | 14.6 |
| dev-AAPL | 365 | slice shortcut | 34.35 | 0.094 | 0.0 | 16.8 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.67 | 1.456 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.63 | 1.463 | 10.0 | 0.0 | {'partial': 90} |

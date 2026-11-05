# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.8 | 0.127 | 39.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.44 | 0.048 | 8.3 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 36.35 | 0.1 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.87 | 0.035 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 1.96 | 0.065 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.41 | 0.047 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 25.24 | 0.069 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.32 | 0.047 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.96 | 0.065 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.31 | 0.044 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 23.57 | 0.065 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 16.21 | 0.044 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 24.4 | 0.813 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 76.03 | 0.845 | 10.1 | 0.0 | {'partial': 90} |

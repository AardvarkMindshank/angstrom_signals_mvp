# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 7.99 | 0.266 | 42.3 | 8.0 |
| synthetic-crypto-s11 | 30 | slice shortcut | 5.11 | 0.17 | 7.7 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 85.24 | 0.234 | 10.5 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 51.64 | 0.141 | 12.6 | 39.9 |
| dev-BTC-USD | 30 | exact | 3.21 | 0.107 | 0.0 | 4.1 |
| dev-BTC-USD | 30 | slice shortcut | 2.4 | 0.08 | 0.0 | 5.1 |
| dev-BTC-USD | 365 | exact | 40.09 | 0.11 | 0.5 | 15.3 |
| dev-BTC-USD | 365 | slice shortcut | 29.71 | 0.081 | 0.0 | 16.6 |
| dev-AAPL | 30 | exact | 3.12 | 0.104 | 0.0 | 4.8 |
| dev-AAPL | 30 | slice shortcut | 2.31 | 0.077 | 0.0 | 5.5 |
| dev-AAPL | 365 | exact | 38.0 | 0.104 | 0.1 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 27.82 | 0.076 | 0.0 | 16.2 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 29.25 | 0.975 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 87.96 | 0.977 | 10.0 | 0.0 | {'partial': 90} |

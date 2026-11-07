# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.68 | 0.156 | 41.2 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.05 | 0.068 | 1.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 49.03 | 0.134 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 18.29 | 0.05 | 1.6 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.84 | 0.095 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.99 | 0.066 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 36.12 | 0.099 | 1.0 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 24.4 | 0.067 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.81 | 0.094 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.91 | 0.064 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 33.55 | 0.092 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 22.31 | 0.061 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.69 | 1.09 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 98.94 | 1.099 | 10.0 | 0.0 | {'partial': 90} |

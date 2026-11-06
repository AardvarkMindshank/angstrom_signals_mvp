# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 5.01 | 0.167 | 38.7 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.07 | 0.069 | 7.1 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 52.1 | 0.143 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 16.1 | 0.044 | 2.5 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.6 | 0.087 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.75 | 0.058 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 32.26 | 0.088 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 22.15 | 0.061 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.69 | 0.09 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.77 | 0.059 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 32.43 | 0.089 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 22.27 | 0.061 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 33.57 | 1.119 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 100.46 | 1.116 | 10.0 | 0.0 | {'partial': 90} |

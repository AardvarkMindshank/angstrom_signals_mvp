# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.3 | 0.11 | 38.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.38 | 0.046 | 1.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 33.15 | 0.091 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.01 | 0.033 | 2.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 1.91 | 0.064 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.32 | 0.044 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 24.01 | 0.066 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 16.3 | 0.045 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.87 | 0.062 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.19 | 0.04 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 21.26 | 0.058 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 14.14 | 0.039 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 22.63 | 0.754 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 67.77 | 0.753 | 10.1 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.22 | 0.107 | 38.9 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.39 | 0.046 | -0.1 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 34.64 | 0.095 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.87 | 0.035 | 1.8 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.03 | 0.068 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.37 | 0.046 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 24.39 | 0.067 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.06 | 0.047 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.86 | 0.062 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.22 | 0.041 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 22.49 | 0.062 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.02 | 0.041 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 22.69 | 0.756 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 68.59 | 0.762 | 10.0 | 0.0 | {'partial': 90} |

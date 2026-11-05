# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.08 | 0.103 | 38.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.33 | 0.044 | 8.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 32.94 | 0.09 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.52 | 0.034 | 1.9 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.05 | 0.068 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.43 | 0.048 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 27.0 | 0.074 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.75 | 0.049 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.94 | 0.065 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.34 | 0.045 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 23.44 | 0.064 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.38 | 0.042 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 24.54 | 0.818 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 74.85 | 0.832 | 10.0 | 0.0 | {'partial': 90} |

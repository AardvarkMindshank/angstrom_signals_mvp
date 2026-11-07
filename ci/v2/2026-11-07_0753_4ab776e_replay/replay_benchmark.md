# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.62 | 0.121 | 38.8 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.47 | 0.049 | 1.8 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 38.03 | 0.104 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.94 | 0.035 | 14.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.1 | 0.07 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.39 | 0.046 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 26.06 | 0.071 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.1 | 0.047 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.05 | 0.068 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.35 | 0.045 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 24.85 | 0.068 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.96 | 0.044 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 25.37 | 0.846 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 76.15 | 0.846 | 10.0 | 0.0 | {'partial': 90} |

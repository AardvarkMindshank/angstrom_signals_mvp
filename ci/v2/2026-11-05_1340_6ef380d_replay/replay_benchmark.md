# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.7 | 0.123 | 38.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.52 | 0.051 | 1.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 39.8 | 0.109 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 12.65 | 0.035 | 2.2 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.08 | 0.069 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.44 | 0.048 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 26.6 | 0.073 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.66 | 0.048 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.91 | 0.064 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.32 | 0.044 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 24.51 | 0.067 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 16.38 | 0.045 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 25.49 | 0.85 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 75.63 | 0.84 | 10.1 | 0.0 | {'partial': 90} |

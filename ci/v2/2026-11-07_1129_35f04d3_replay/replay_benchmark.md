# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.28 | 0.109 | 38.6 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.45 | 0.048 | -0.2 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 33.63 | 0.092 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 11.97 | 0.033 | 2.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.09 | 0.07 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.32 | 0.044 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 24.04 | 0.066 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 17.64 | 0.048 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.01 | 0.067 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.33 | 0.044 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 24.11 | 0.066 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.17 | 0.042 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 22.72 | 0.757 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 69.44 | 0.772 | 10.0 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.15 | 0.105 | 38.5 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.29 | 0.043 | 8.5 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 32.83 | 0.09 | 12.1 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 11.6 | 0.032 | 2.2 | 39.2 |
| dev-BTC-USD | 30 | exact | 1.84 | 0.061 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.28 | 0.043 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 23.17 | 0.063 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 16.1 | 0.044 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.8 | 0.06 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.24 | 0.041 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 22.88 | 0.063 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 15.07 | 0.041 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 23.17 | 0.772 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 69.35 | 0.771 | 10.0 | 0.0 | {'partial': 90} |

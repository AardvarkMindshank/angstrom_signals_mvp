# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.07 | 0.102 | 39.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.31 | 0.044 | 1.7 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 31.68 | 0.087 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 11.65 | 0.032 | 2.2 | 39.2 |
| dev-BTC-USD | 30 | exact | 1.83 | 0.061 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.27 | 0.042 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 23.1 | 0.063 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 15.85 | 0.043 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 1.78 | 0.059 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.28 | 0.043 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 22.4 | 0.061 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 14.77 | 0.04 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 22.06 | 0.735 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 68.2 | 0.758 | 10.1 | 0.0 | {'partial': 90} |

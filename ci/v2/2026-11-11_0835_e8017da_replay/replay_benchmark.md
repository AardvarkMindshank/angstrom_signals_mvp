# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.43 | 0.214 | 39.7 | 7.6 |
| synthetic-crypto-s11 | 30 | slice shortcut | 4.25 | 0.142 | 7.0 | 25.8 |
| synthetic-crypto-s11 | 365 | exact | 66.9 | 0.183 | 0.9 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 42.48 | 0.116 | 8.1 | 39.9 |
| dev-BTC-USD | 30 | exact | 2.6 | 0.087 | 0.0 | 3.8 |
| dev-BTC-USD | 30 | slice shortcut | 1.92 | 0.064 | 0.0 | 4.8 |
| dev-BTC-USD | 365 | exact | 31.06 | 0.085 | 0.5 | 15.4 |
| dev-BTC-USD | 365 | slice shortcut | 21.93 | 0.06 | 0.0 | 16.7 |
| dev-AAPL | 30 | exact | 2.17 | 0.072 | 0.0 | 4.5 |
| dev-AAPL | 30 | slice shortcut | 1.59 | 0.053 | 0.0 | 5.2 |
| dev-AAPL | 365 | exact | 28.03 | 0.077 | 0.0 | 14.5 |
| dev-AAPL | 365 | slice shortcut | 19.0 | 0.052 | 0.0 | 16.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 23.72 | 0.791 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 71.5 | 0.794 | 10.0 | 0.0 | {'partial': 90} |

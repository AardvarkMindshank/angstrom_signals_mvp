# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.4 | 0.147 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.95 | 0.065 | 1.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 45.62 | 0.125 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.27 | 0.047 | 2.6 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.7 | 0.09 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.87 | 0.062 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 33.53 | 0.092 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 23.09 | 0.063 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.62 | 0.087 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.8 | 0.06 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 31.65 | 0.087 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.32 | 0.058 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.23 | 1.041 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 93.99 | 1.044 | 10.1 | 0.0 | {'partial': 90} |

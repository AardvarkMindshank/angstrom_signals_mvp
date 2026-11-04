# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.05 | 0.202 | 41.5 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.56 | 0.085 | 8.5 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 62.82 | 0.172 | 15.4 | 21.2 |
| synthetic-crypto-s11 | 365 | slice shortcut | 22.15 | 0.061 | 1.3 | 42.0 |
| dev-BTC-USD | 30 | exact | 3.7 | 0.123 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.52 | 0.084 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 45.95 | 0.126 | 0.7 | 19.7 |
| dev-BTC-USD | 365 | slice shortcut | 31.25 | 0.086 | 0.0 | 21.3 |
| dev-AAPL | 30 | exact | 3.63 | 0.121 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.45 | 0.082 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 43.63 | 0.12 | 0.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 28.76 | 0.079 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.63 | 1.454 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 129.11 | 1.435 | 10.0 | 0.0 | {'partial': 90} |

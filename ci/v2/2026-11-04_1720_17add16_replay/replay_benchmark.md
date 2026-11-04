# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.05 | 0.202 | 41.6 | 6.2 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.56 | 0.085 | 8.6 | 23.8 |
| synthetic-crypto-s11 | 365 | exact | 63.02 | 0.173 | 15.5 | 21.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 21.98 | 0.06 | 15.0 | 42.0 |
| dev-BTC-USD | 30 | exact | 3.77 | 0.126 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.55 | 0.085 | 0.0 | 3.7 |
| dev-BTC-USD | 365 | exact | 46.55 | 0.128 | 1.0 | 19.6 |
| dev-BTC-USD | 365 | slice shortcut | 31.18 | 0.085 | 0.0 | 21.4 |
| dev-AAPL | 30 | exact | 3.57 | 0.119 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.42 | 0.081 | 0.0 | 4.1 |
| dev-AAPL | 365 | exact | 43.0 | 0.118 | 0.0 | 17.6 |
| dev-AAPL | 365 | slice shortcut | 28.21 | 0.077 | 0.0 | 19.7 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.62 | 1.454 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 131.09 | 1.457 | 10.0 | 0.0 | {'partial': 90} |

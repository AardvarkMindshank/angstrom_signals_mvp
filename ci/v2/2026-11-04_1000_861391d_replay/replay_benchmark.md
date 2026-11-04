# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.41 | 0.214 | 40.9 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 3.35 | 0.112 | 8.5 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 66.92 | 0.183 | 15.8 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 31.29 | 0.086 | 6.2 | 42.3 |
| dev-BTC-USD | 30 | exact | 3.86 | 0.129 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 3.29 | 0.11 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 48.2 | 0.132 | 0.9 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 40.45 | 0.111 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 3.85 | 0.128 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 3.25 | 0.108 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 45.5 | 0.125 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 37.83 | 0.104 | 0.0 | 20.0 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 43.64 | 1.455 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 130.66 | 1.452 | 10.0 | 0.0 | {'partial': 90} |

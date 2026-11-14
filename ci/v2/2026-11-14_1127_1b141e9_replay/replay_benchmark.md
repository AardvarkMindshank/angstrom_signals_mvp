# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.56 | 0.219 | 40.3 | 8.0 |
| synthetic-crypto-s11 | 30 | slice shortcut | 4.31 | 0.144 | 8.2 | 26.1 |
| synthetic-crypto-s11 | 365 | exact | 71.14 | 0.195 | 10.5 | 18.3 |
| synthetic-crypto-s11 | 365 | slice shortcut | 49.34 | 0.135 | 8.4 | 39.9 |
| dev-BTC-USD | 30 | exact | 2.55 | 0.085 | 0.0 | 4.1 |
| dev-BTC-USD | 30 | slice shortcut | 1.96 | 0.065 | 0.0 | 5.1 |
| dev-BTC-USD | 365 | exact | 31.72 | 0.087 | 0.4 | 15.3 |
| dev-BTC-USD | 365 | slice shortcut | 24.56 | 0.067 | 0.0 | 16.6 |
| dev-AAPL | 30 | exact | 2.42 | 0.081 | 0.0 | 4.8 |
| dev-AAPL | 30 | slice shortcut | 1.87 | 0.062 | 0.0 | 5.5 |
| dev-AAPL | 365 | exact | 31.52 | 0.086 | 0.0 | 14.4 |
| dev-AAPL | 365 | slice shortcut | 22.61 | 0.062 | 0.0 | 16.2 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 22.34 | 0.745 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 67.75 | 0.753 | 10.0 | 0.0 | {'partial': 90} |

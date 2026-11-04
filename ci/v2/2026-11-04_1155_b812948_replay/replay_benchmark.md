# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.32 | 0.144 | 40.9 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.28 | 0.076 | 1.6 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 44.37 | 0.122 | 15.8 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 21.17 | 0.058 | 0.9 | 42.3 |
| dev-BTC-USD | 30 | exact | 2.61 | 0.087 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 2.24 | 0.075 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 32.31 | 0.089 | 0.8 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 27.53 | 0.075 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 2.54 | 0.085 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 2.18 | 0.073 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 30.97 | 0.085 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 25.48 | 0.07 | 0.0 | 20.0 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.27 | 1.042 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 93.91 | 1.043 | 10.0 | 0.0 | {'partial': 90} |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.79 | 0.16 | 41.0 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.01 | 0.067 | 1.3 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 48.1 | 0.132 | 12.1 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.64 | 0.048 | 2.4 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.88 | 0.096 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.99 | 0.066 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 35.87 | 0.098 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 24.23 | 0.066 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.91 | 0.097 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.89 | 0.063 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 33.33 | 0.091 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.91 | 0.06 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 32.11 | 1.07 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 95.93 | 1.066 | 10.0 | 0.0 | {'partial': 90} |

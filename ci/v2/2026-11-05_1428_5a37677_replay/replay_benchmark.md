# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.75 | 0.158 | 41.6 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.0 | 0.067 | 8.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 49.16 | 0.135 | 11.9 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.53 | 0.048 | 2.4 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.83 | 0.094 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 1.95 | 0.065 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 35.2 | 0.096 | 0.9 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 24.07 | 0.066 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.76 | 0.092 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.89 | 0.063 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 33.41 | 0.092 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 22.03 | 0.06 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.85 | 1.062 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 95.69 | 1.063 | 10.1 | 0.0 | {'partial': 90} |

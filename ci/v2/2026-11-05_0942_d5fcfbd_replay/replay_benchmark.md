# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 4.83 | 0.161 | 41.1 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.0 | 0.067 | 8.4 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 50.31 | 0.138 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 17.56 | 0.048 | 2.1 | 39.2 |
| dev-BTC-USD | 30 | exact | 2.94 | 0.098 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.0 | 0.067 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 36.02 | 0.099 | 1.0 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 24.43 | 0.067 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.79 | 0.093 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.86 | 0.062 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 33.92 | 0.093 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 21.64 | 0.059 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 31.91 | 1.064 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 95.09 | 1.057 | 10.1 | 0.0 | {'partial': 90} |

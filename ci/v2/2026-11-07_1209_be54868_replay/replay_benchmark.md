# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 5.23 | 0.174 | 38.6 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.16 | 0.072 | 8.9 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 55.11 | 0.151 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 19.06 | 0.052 | 2.4 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.07 | 0.102 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.09 | 0.07 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 38.27 | 0.105 | 1.0 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 25.41 | 0.07 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 2.97 | 0.099 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 1.97 | 0.066 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 35.95 | 0.098 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 23.29 | 0.064 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 35.4 | 1.18 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 106.76 | 1.186 | 10.0 | 0.0 | {'partial': 90} |

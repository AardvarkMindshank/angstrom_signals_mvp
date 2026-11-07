# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.27 | 0.209 | 41.6 | 6.8 |
| synthetic-crypto-s11 | 30 | slice shortcut | 2.71 | 0.09 | 1.8 | 24.4 |
| synthetic-crypto-s11 | 365 | exact | 65.5 | 0.179 | 12.0 | 18.6 |
| synthetic-crypto-s11 | 365 | slice shortcut | 24.44 | 0.067 | 2.3 | 39.2 |
| dev-BTC-USD | 30 | exact | 3.98 | 0.133 | 0.0 | 3.3 |
| dev-BTC-USD | 30 | slice shortcut | 2.67 | 0.089 | 0.0 | 4.2 |
| dev-BTC-USD | 365 | exact | 48.54 | 0.133 | 0.8 | 16.7 |
| dev-BTC-USD | 365 | slice shortcut | 32.91 | 0.09 | 0.0 | 18.0 |
| dev-AAPL | 30 | exact | 3.88 | 0.129 | 0.0 | 4.0 |
| dev-AAPL | 30 | slice shortcut | 2.63 | 0.088 | 0.0 | 4.7 |
| dev-AAPL | 365 | exact | 46.41 | 0.127 | 0.0 | 15.4 |
| dev-AAPL | 365 | slice shortcut | 30.82 | 0.084 | 0.0 | 17.4 |

## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)

| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | 42.95 | 1.432 | 5.9 | 0.0 | {'partial': 30} |
| synthetic-crypto-s11 | 90 | 129.68 | 1.441 | 10.0 | 0.0 | {'partial': 90} |

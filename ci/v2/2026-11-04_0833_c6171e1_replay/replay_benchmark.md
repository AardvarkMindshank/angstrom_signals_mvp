# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.24 | 0.108 | 38.4 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.67 | 0.056 | 8.6 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 32.79 | 0.09 | 15.7 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 15.84 | 0.043 | 15.1 | 42.3 |
| dev-BTC-USD | 30 | exact | 1.97 | 0.066 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 1.74 | 0.058 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 24.2 | 0.066 | 0.7 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 20.02 | 0.055 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 1.83 | 0.061 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 1.6 | 0.053 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 22.51 | 0.062 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 19.18 | 0.053 | 0.0 | 20.0 |

# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 3.56 | 0.119 | 39.0 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 1.78 | 0.059 | 8.6 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 35.25 | 0.097 | 15.8 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 16.68 | 0.046 | 2.5 | 42.3 |
| dev-BTC-USD | 30 | exact | 2.07 | 0.069 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 1.78 | 0.059 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 25.76 | 0.071 | 0.7 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 20.98 | 0.057 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 1.9 | 0.063 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 1.62 | 0.054 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 23.18 | 0.064 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 18.97 | 0.052 | 0.0 | 20.0 |

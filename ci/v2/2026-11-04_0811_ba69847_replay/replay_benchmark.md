# Replay benchmark

Every 1D candle signal incl. multi-timeframe alignment, per step; certification mode (no certification lookup), real indicators.

| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |
|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | 30 | exact | 6.26 | 0.209 | 41.6 | 6.3 |
| synthetic-crypto-s11 | 30 | slice shortcut | 3.3 | 0.11 | 8.8 | 24.1 |
| synthetic-crypto-s11 | 365 | exact | 65.35 | 0.179 | 15.7 | 21.4 |
| synthetic-crypto-s11 | 365 | slice shortcut | 31.54 | 0.086 | 1.1 | 42.3 |
| dev-BTC-USD | 30 | exact | 3.93 | 0.131 | 0.0 | 2.7 |
| dev-BTC-USD | 30 | slice shortcut | 3.3 | 0.11 | 0.0 | 4.0 |
| dev-BTC-USD | 365 | exact | 47.6 | 0.13 | 0.7 | 19.8 |
| dev-BTC-USD | 365 | slice shortcut | 40.47 | 0.111 | 0.0 | 21.6 |
| dev-AAPL | 30 | exact | 3.79 | 0.126 | 0.0 | 3.4 |
| dev-AAPL | 30 | slice shortcut | 3.21 | 0.107 | 0.0 | 4.4 |
| dev-AAPL | 365 | exact | 45.56 | 0.125 | 0.0 | 17.9 |
| dev-AAPL | 365 | slice shortcut | 38.34 | 0.105 | 0.0 | 20.0 |

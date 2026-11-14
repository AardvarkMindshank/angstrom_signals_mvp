# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 208 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 45.7 | 0.762 | 29.1 | 62.6 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 43.8 | 0.73 | 32.8 | 22.2 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.4 | 0.589 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.8 | 0.597 | 46.9 | 17.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 21.7 | 0.362 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 20.7 | 0.345 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.0 | 0.234 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.0 | 0.233 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 8.8 | 0.147 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.3 | 0.121 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.1 | 0.085 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.0 | 0.084 | 10.8 | 0.0 | 50 | 0  |

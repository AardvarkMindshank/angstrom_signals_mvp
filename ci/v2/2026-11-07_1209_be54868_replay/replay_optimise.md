# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 72.5 | 1.208 | 29.0 | 62.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 69.5 | 1.159 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 54.2 | 0.904 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 54.4 | 0.906 | 46.9 | 16.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 35.4 | 0.589 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 33.2 | 0.554 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 22.1 | 0.368 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 22.0 | 0.367 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 14.5 | 0.242 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 11.9 | 0.199 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 8.2 | 0.137 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 8.2 | 0.136 | 10.8 | 0.0 | 50 | 0  |

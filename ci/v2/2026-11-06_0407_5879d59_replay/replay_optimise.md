# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 48.1 | 0.802 | 29.0 | 61.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 43.2 | 0.72 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 37.2 | 0.62 | 30.3 | 0.2 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 38.6 | 0.644 | 46.9 | 29.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 25.4 | 0.424 | 7.3 | -22.1 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 23.7 | 0.394 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 15.9 | 0.265 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 15.5 | 0.259 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.2 | 0.17 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.3 | 0.138 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.8 | 0.096 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.8 | 0.097 | 10.8 | 0.0 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 47.1 | 0.785 | 29.0 | 61.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 43.5 | 0.725 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 34.6 | 0.577 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 34.8 | 0.58 | 46.9 | 17.4 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 21.3 | 0.355 | 7.3 | -14.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 20.2 | 0.337 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 13.7 | 0.229 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 13.7 | 0.228 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 8.9 | 0.148 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.2 | 0.119 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.1 | 0.085 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.0 | 0.084 | 10.8 | 0.0 | 50 | 0  |

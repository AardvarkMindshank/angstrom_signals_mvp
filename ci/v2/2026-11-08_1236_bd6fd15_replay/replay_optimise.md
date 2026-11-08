# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 87.9 | 1.465 | 29.0 | 64.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.3 | 1.406 | 32.8 | 23.0 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.5 | 1.108 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.5 | 1.109 | 46.9 | 27.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.3 | 0.704 | 7.3 | -8.3 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 39.8 | 0.664 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 26.9 | 0.449 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 26.8 | 0.447 | 18.9 | 1.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.4 | 0.29 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.3 | 0.239 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.0 | 0.167 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 9.9 | 0.166 | 10.8 | 0.0 | 50 | 0  |

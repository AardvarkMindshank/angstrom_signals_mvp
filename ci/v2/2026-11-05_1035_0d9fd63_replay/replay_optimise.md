# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 92 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.4 | 1.473 | 29.0 | 64.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.7 | 1.411 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.1 | 1.118 | 30.3 | 1.1 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.0 | 1.117 | 46.9 | 28.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 43.7 | 0.728 | 7.3 | -11.4 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 41.5 | 0.692 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.7 | 0.461 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.6 | 0.459 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.2 | 0.303 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.8 | 0.247 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.3 | 0.171 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.2 | 0.17 | 10.8 | 0.0 | 50 | 0  |

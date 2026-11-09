# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 89.3 | 1.489 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 85.5 | 1.425 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.4 | 1.124 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.2 | 1.121 | 46.9 | 17.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 43.5 | 0.726 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 41.0 | 0.683 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.8 | 0.463 | 12.6 | 0.2 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.4 | 0.456 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.1 | 0.301 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 15.0 | 0.25 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.4 | 0.174 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.3 | 0.172 | 10.8 | 0.0 | 50 | 0  |

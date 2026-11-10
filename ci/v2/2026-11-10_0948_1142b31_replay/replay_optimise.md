# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 118 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 89.4 | 1.489 | 29.0 | 64.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 85.4 | 1.424 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.3 | 1.122 | 30.3 | 0.2 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.1 | 1.119 | 46.9 | 25.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 43.1 | 0.719 | 7.3 | -30.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.3 | 0.671 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.1 | 0.452 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.1 | 0.452 | 18.9 | 1.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.6 | 0.294 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.5 | 0.241 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.169 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

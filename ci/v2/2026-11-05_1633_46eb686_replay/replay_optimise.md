# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.0 | 1.467 | 29.0 | 64.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.8 | 1.414 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.9 | 1.115 | 30.3 | 0.1 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.9 | 1.115 | 46.9 | 25.0 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.1 | 0.702 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 39.6 | 0.661 | 17.0 | -17.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.0 | 0.45 | 12.6 | 0.2 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.0 | 0.45 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.5 | 0.291 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.4 | 0.241 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.169 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

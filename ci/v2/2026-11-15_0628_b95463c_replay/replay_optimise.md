# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 208 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 66.1 | 1.101 | 29.1 | 65.0 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 63.8 | 1.063 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.8 | 0.813 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.6 | 0.809 | 46.9 | 17.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 33.2 | 0.553 | 7.3 | -10.6 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 30.7 | 0.512 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 20.3 | 0.338 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 20.3 | 0.338 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 13.5 | 0.225 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 11.0 | 0.184 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.5 | 0.125 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.5 | 0.125 | 10.8 | 0.0 | 50 | 0  |

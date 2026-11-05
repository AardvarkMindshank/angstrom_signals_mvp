# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 93 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 49.2 | 0.82 | 29.0 | 61.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 47.8 | 0.797 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 37.8 | 0.63 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 38.7 | 0.646 | 46.9 | 17.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 24.3 | 0.405 | 7.3 | -18.4 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.5 | 0.359 | 17.0 | -8.5 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.4 | 0.241 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 15.3 | 0.255 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.7 | 0.161 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.8 | 0.131 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.6 | 0.093 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.6 | 0.094 | 10.8 | 0.0 | 50 | 0  |

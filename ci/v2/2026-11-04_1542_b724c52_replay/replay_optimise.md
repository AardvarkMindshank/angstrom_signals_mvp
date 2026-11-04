# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 87.1 | 1.452 | 29.0 | 64.2 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 83.4 | 1.391 | 32.8 | 23.2 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.4 | 1.106 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.2 | 1.104 | 46.9 | 16.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 41.7 | 0.695 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 39.3 | 0.655 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 26.7 | 0.444 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 26.6 | 0.443 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.1 | 0.286 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.2 | 0.236 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 9.9 | 0.165 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 9.9 | 0.165 | 10.8 | 0.0 | 50 | 0  |

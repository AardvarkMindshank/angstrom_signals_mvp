# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 49.4 | 0.824 | 29.0 | 62.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 46.6 | 0.777 | 32.8 | 22.3 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.6 | 0.594 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.0 | 0.584 | 46.9 | 28.6 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 22.6 | 0.377 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.0 | 0.349 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.3 | 0.238 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.0 | 0.233 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.3 | 0.155 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.5 | 0.125 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.2 | 0.087 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.2 | 0.087 | 10.8 | 0.0 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 92.5 | 1.542 | 29.0 | 65.0 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 89.4 | 1.491 | 32.8 | 23.1 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.9 | 1.131 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.4 | 1.124 | 46.9 | 17.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 44.6 | 0.743 | 7.3 | -22.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 41.9 | 0.699 | 17.0 | 0.2 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 28.0 | 0.466 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.7 | 0.462 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.4 | 0.306 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 15.2 | 0.253 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.4 | 0.173 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.3 | 0.172 | 10.8 | 0.0 | 50 | 0  |

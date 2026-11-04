# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 93 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 90.0 | 1.499 | 29.0 | 65.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 86.6 | 1.443 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.7 | 1.129 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.3 | 1.122 | 46.9 | 27.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 44.1 | 0.735 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 41.2 | 0.687 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.6 | 0.46 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.5 | 0.459 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.1 | 0.301 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.5 | 0.242 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.168 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.1 | 0.168 | 10.8 | 0.0 | 50 | 0  |

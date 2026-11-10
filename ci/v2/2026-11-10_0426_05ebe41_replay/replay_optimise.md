# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.7 | 1.478 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.9 | 1.414 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.3 | 1.121 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.6 | 1.126 | 46.9 | 29.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.5 | 0.709 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.2 | 0.67 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.6 | 0.46 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.1 | 0.452 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.6 | 0.293 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.4 | 0.24 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.0 | 0.167 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.1 | 1.469 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.2 | 1.403 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.0 | 1.117 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.8 | 1.113 | 46.9 | 31.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.2 | 0.703 | 7.3 | -21.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.0 | 0.666 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 26.8 | 0.447 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 26.7 | 0.445 | 18.9 | 1.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.2 | 0.287 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.2 | 0.237 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.168 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

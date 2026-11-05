# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 89.0 | 1.484 | 29.0 | 64.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 85.1 | 1.419 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.3 | 1.122 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.3 | 1.121 | 46.9 | 16.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 43.3 | 0.721 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.8 | 0.679 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.5 | 0.458 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.4 | 0.456 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.9 | 0.298 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.7 | 0.245 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.3 | 0.171 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.2 | 0.17 | 10.8 | 0.0 | 50 | 0  |

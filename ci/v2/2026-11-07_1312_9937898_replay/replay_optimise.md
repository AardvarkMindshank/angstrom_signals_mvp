# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 87.1 | 1.451 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 83.0 | 1.384 | 32.8 | 22.4 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 65.8 | 1.097 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 65.8 | 1.097 | 46.9 | 17.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 41.5 | 0.691 | 7.3 | -28.4 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 39.2 | 0.654 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 26.5 | 0.442 | 12.6 | 0.2 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 26.3 | 0.438 | 18.9 | 2.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.1 | 0.284 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.1 | 0.235 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 9.9 | 0.165 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 9.9 | 0.165 | 10.8 | 0.0 | 50 | 0  |

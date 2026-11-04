# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.1 | 1.468 | 29.0 | 65.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.4 | 1.406 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.2 | 1.12 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.3 | 1.121 | 46.9 | 16.6 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 41.6 | 0.694 | 7.3 | -19.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 39.3 | 0.655 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 26.9 | 0.448 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 26.9 | 0.449 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.4 | 0.291 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.3 | 0.239 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.168 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

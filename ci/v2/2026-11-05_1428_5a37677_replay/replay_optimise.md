# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 65.2 | 1.086 | 29.0 | 64.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 62.7 | 1.046 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.6 | 0.81 | 30.3 | -1.8 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 49.0 | 0.817 | 46.9 | 31.4 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 32.7 | 0.546 | 7.3 | -17.2 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 30.5 | 0.509 | 17.0 | -15.6 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 20.2 | 0.336 | 12.6 | 0.3 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 20.2 | 0.336 | 18.9 | 3.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 13.4 | 0.223 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.9 | 0.181 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.5 | 0.125 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.4 | 0.124 | 10.8 | 0.0 | 50 | 0  |

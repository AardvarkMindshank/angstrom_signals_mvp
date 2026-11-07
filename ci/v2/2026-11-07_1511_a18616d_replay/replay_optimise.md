# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 66.2 | 1.104 | 29.0 | 64.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 63.5 | 1.059 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 49.1 | 0.818 | 30.3 | 0.2 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 49.1 | 0.818 | 46.9 | 25.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 33.0 | 0.55 | 7.3 | -28.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 31.0 | 0.516 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 20.4 | 0.34 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 20.1 | 0.334 | 18.9 | 1.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.9 | 0.215 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.8 | 0.18 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.4 | 0.124 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.4 | 0.123 | 10.8 | 0.0 | 50 | 0  |

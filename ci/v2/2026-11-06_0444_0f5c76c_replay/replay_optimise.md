# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 68.4 | 1.14 | 29.0 | 62.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 65.5 | 1.091 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 50.6 | 0.844 | 30.3 | 0.2 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 50.1 | 0.834 | 46.9 | 17.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 32.8 | 0.547 | 7.3 | -13.1 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 31.3 | 0.521 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 20.9 | 0.349 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 21.0 | 0.35 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 14.0 | 0.233 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 11.5 | 0.191 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.8 | 0.131 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.8 | 0.13 | 10.8 | 0.0 | 50 | 0  |

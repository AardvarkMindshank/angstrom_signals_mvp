# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 165 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 47.9 | 0.799 | 29.1 | 62.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 44.9 | 0.748 | 32.8 | 22.5 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 36.4 | 0.606 | 30.3 | 0.1 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 37.0 | 0.616 | 46.9 | 28.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 23.0 | 0.383 | 7.3 | -19.4 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.7 | 0.361 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.2 | 0.236 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.2 | 0.237 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.4 | 0.157 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.9 | 0.132 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.4 | 0.089 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.4 | 0.091 | 10.8 | 0.0 | 50 | 0  |

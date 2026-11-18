# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 208 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.3 | 1.071 | 29.1 | 65.0 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 61.4 | 1.023 | 32.8 | 22.4 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.2 | 0.804 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.3 | 0.805 | 46.9 | 17.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 30.9 | 0.515 | 7.3 | -30.4 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 28.8 | 0.481 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.5 | 0.325 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 19.5 | 0.326 | 18.9 | 1.7 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.6 | 0.211 | 5.1 | -9.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.4 | 0.174 | 12.1 | 2.9 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.3 | 0.121 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.2 | 0.121 | 10.8 | 0.3 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 93 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 58.5 | 0.975 | 29.0 | 62.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 56.0 | 0.933 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 43.4 | 0.723 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 43.2 | 0.72 | 46.9 | 17.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 28.7 | 0.479 | 7.3 | -24.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 26.8 | 0.446 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 17.7 | 0.295 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 17.7 | 0.294 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 11.8 | 0.197 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 9.7 | 0.161 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 6.6 | 0.11 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 6.6 | 0.109 | 10.8 | 0.0 | 50 | 0  |

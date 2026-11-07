# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 49.1 | 0.818 | 29.0 | 62.2 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 48.5 | 0.808 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 37.0 | 0.616 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 37.3 | 0.622 | 46.9 | 25.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 24.4 | 0.407 | 7.3 | -27.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.7 | 0.361 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.7 | 0.244 | 12.6 | 0.2 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 15.0 | 0.251 | 18.9 | 0.1 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.8 | 0.164 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.1 | 0.134 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.6 | 0.093 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.8 | 0.096 | 10.8 | 0.0 | 50 | 0  |

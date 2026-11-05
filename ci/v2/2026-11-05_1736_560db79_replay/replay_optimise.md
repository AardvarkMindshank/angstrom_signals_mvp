# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 51.0 | 0.849 | 29.0 | 62.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 47.6 | 0.793 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 37.5 | 0.625 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 39.9 | 0.666 | 46.9 | 27.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 25.2 | 0.42 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 23.4 | 0.39 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 15.2 | 0.253 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.7 | 0.245 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.1 | 0.169 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.2 | 0.137 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.8 | 0.097 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.8 | 0.097 | 10.8 | 0.0 | 50 | 0  |

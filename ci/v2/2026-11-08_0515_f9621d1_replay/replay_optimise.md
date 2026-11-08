# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 52.4 | 0.874 | 29.0 | 62.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 50.6 | 0.843 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 39.1 | 0.651 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 38.7 | 0.645 | 46.9 | 27.5 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 25.8 | 0.43 | 7.3 | -15.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 24.0 | 0.4 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 16.5 | 0.275 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 16.0 | 0.266 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.6 | 0.177 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.7 | 0.144 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.9 | 0.098 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.8 | 0.097 | 10.8 | 0.0 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 51.0 | 0.849 | 29.0 | 62.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 47.6 | 0.793 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 36.0 | 0.6 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.2 | 0.587 | 46.9 | 25.4 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 23.8 | 0.396 | 7.3 | -24.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.4 | 0.357 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.4 | 0.24 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.8 | 0.247 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.0 | 0.167 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.1 | 0.135 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.6 | 0.094 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.5 | 0.091 | 10.8 | 0.0 | 50 | 0  |

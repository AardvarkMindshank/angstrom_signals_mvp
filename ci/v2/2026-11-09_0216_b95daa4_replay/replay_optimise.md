# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 47.5 | 0.791 | 29.0 | 62.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 45.9 | 0.766 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.8 | 0.597 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 36.3 | 0.605 | 46.9 | 17.5 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 23.1 | 0.385 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.5 | 0.358 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.6 | 0.243 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.6 | 0.243 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.4 | 0.157 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.8 | 0.131 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.4 | 0.09 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.5 | 0.092 | 10.8 | 0.0 | 50 | 0  |

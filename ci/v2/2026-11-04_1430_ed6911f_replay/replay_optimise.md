# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 48.4 | 0.806 | 29.0 | 61.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 47.0 | 0.783 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 36.4 | 0.607 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 36.2 | 0.603 | 46.8 | 16.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 23.2 | 0.386 | 7.3 | -21.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 22.1 | 0.369 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 15.0 | 0.25 | 12.5 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.9 | 0.249 | 18.8 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.0 | 0.166 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.3 | 0.139 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.6 | 0.093 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.5 | 0.092 | 10.8 | 0.0 | 50 | 0  |

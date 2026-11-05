# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 51.1 | 0.852 | 29.0 | 62.0 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 48.0 | 0.801 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 36.8 | 0.614 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 37.2 | 0.621 | 46.9 | 16.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 23.2 | 0.386 | 7.3 | -11.7 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 22.5 | 0.375 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 15.7 | 0.262 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 15.3 | 0.255 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.1 | 0.168 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.6 | 0.143 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.9 | 0.098 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.7 | 0.095 | 10.8 | 0.0 | 50 | 0  |

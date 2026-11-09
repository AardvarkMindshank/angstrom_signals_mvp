# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 45.4 | 0.757 | 29.0 | 62.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 44.5 | 0.742 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.4 | 0.59 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 34.0 | 0.566 | 46.9 | 18.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 21.8 | 0.363 | 7.3 | -21.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 20.5 | 0.342 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 13.8 | 0.23 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.0 | 0.233 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.0 | 0.151 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.4 | 0.123 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.2 | 0.087 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.3 | 0.088 | 10.8 | 0.0 | 50 | 0  |

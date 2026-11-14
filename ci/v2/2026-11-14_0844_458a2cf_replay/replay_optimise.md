# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 187 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 72.3 | 1.206 | 29.1 | 62.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 69.3 | 1.155 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 54.0 | 0.9 | 30.3 | -0.4 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 54.1 | 0.901 | 46.9 | 26.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 35.8 | 0.596 | 7.3 | -26.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 33.5 | 0.559 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 22.2 | 0.37 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 22.1 | 0.369 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 14.8 | 0.246 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 12.1 | 0.202 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 8.3 | 0.138 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 8.2 | 0.137 | 10.8 | 0.0 | 50 | 0  |

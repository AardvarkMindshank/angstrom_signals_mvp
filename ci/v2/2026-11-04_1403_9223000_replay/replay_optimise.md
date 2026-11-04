# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 73.5 | 1.225 | 29.0 | 61.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 70.2 | 1.171 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 54.8 | 0.914 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 54.6 | 0.91 | 46.8 | 17.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 35.9 | 0.598 | 7.3 | -23.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 33.6 | 0.56 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 22.3 | 0.372 | 12.5 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 22.3 | 0.372 | 18.8 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 14.8 | 0.247 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 12.1 | 0.202 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 8.3 | 0.138 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 8.2 | 0.137 | 10.8 | 0.0 | 50 | 0  |

# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.6 | 1.477 | 29.0 | 63.5 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 85.3 | 1.422 | 32.8 | 23.3 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.1 | 1.118 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.9 | 1.116 | 46.9 | 16.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.7 | 0.711 | 7.3 | -16.1 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.1 | 0.669 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.2 | 0.453 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.0 | 0.449 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.5 | 0.291 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.4 | 0.241 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.169 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

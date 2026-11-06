# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.9 | 1.482 | 29.0 | 64.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 84.4 | 1.407 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.4 | 1.107 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.3 | 1.104 | 46.9 | 17.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.5 | 0.708 | 7.3 | -12.1 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.5 | 0.675 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.1 | 0.451 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.2 | 0.453 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.5 | 0.292 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.4 | 0.239 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.0 | 0.166 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.0 | 0.167 | 10.8 | 0.0 | 50 | 0  |

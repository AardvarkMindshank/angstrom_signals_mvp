# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 66.6 | 1.109 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 63.5 | 1.058 | 32.9 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.3 | 1.105 | 32.9 | 1.1 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 64.0 | 1.067 | 48.5 | 14.8 | 102 | 0  |
| synthetic-equity-s23 | A exact | 60 | 33.0 | 0.55 | 7.4 | -8.7 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 30.7 | 0.512 | 17.2 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 33.2 | 0.554 | 13.7 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 31.2 | 0.519 | 20.2 | 0.0 | 96 | 0  |
| dev-BTC-USD | A exact | 60 | 13.3 | 0.221 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.7 | 0.178 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 13.4 | 0.223 | 7.0 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 11.1 | 0.185 | 11.8 | -0.0 | 100 | 0  |

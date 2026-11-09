# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 90.1 | 1.502 | 29.0 | 64.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 86.5 | 1.442 | 32.8 | 22.7 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 68.5 | 1.141 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 68.0 | 1.134 | 46.9 | 27.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 44.9 | 0.748 | 7.3 | -14.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 42.9 | 0.715 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 28.2 | 0.469 | 12.6 | 0.2 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.9 | 0.464 | 18.9 | 1.9 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.3 | 0.305 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 15.2 | 0.253 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.5 | 0.176 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.4 | 0.174 | 10.8 | 0.0 | 50 | 0  |

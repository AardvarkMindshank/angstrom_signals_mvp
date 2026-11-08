# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 45.3 | 0.755 | 29.0 | 61.9 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 44.9 | 0.748 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.6 | 0.593 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.2 | 0.587 | 46.9 | 17.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 21.8 | 0.363 | 7.3 | -10.6 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.0 | 0.35 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.1 | 0.236 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.0 | 0.233 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.1 | 0.152 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.3 | 0.122 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.1 | 0.085 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.0 | 0.084 | 10.8 | 0.0 | 50 | 0  |

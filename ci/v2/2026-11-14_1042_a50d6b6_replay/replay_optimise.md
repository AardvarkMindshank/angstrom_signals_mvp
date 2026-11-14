# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 201 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 59.4 | 0.991 | 29.1 | 62.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 56.9 | 0.948 | 32.8 | 22.3 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 44.1 | 0.734 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 43.9 | 0.731 | 46.9 | 18.5 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 29.5 | 0.491 | 7.3 | -27.6 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 27.6 | 0.46 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 18.1 | 0.302 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 18.1 | 0.301 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.1 | 0.201 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 9.8 | 0.164 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 6.7 | 0.112 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 6.7 | 0.111 | 10.8 | 0.0 | 50 | 0  |

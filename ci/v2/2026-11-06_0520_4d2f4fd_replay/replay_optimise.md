# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.4 | 1.074 | 29.0 | 64.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 61.7 | 1.029 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.7 | 0.812 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.3 | 0.805 | 46.9 | 16.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 30.9 | 0.515 | 7.3 | -10.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 28.8 | 0.48 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.6 | 0.327 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 19.4 | 0.324 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.6 | 0.209 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.4 | 0.174 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.3 | 0.121 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.2 | 0.121 | 10.8 | 0.0 | 50 | 0  |

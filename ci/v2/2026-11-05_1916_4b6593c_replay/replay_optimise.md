# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 88.0 | 1.466 | 29.0 | 64.9 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 85.0 | 1.417 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.2 | 1.12 | 30.3 | 1.1 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.5 | 1.125 | 46.9 | 16.8 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.9 | 0.715 | 7.3 | -21.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.5 | 0.675 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.5 | 0.458 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.4 | 0.457 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.1 | 0.301 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.7 | 0.245 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.3 | 0.172 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.2 | 0.171 | 10.8 | 0.0 | 50 | 0  |

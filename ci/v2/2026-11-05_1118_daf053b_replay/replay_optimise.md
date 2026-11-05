# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 92 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.4 | 1.073 | 29.0 | 64.7 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 61.3 | 1.022 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.5 | 0.809 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.3 | 0.804 | 46.9 | 17.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 31.4 | 0.523 | 7.3 | -24.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 29.3 | 0.489 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.8 | 0.33 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 19.7 | 0.329 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.8 | 0.213 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.6 | 0.177 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.4 | 0.123 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.4 | 0.124 | 10.8 | 0.0 | 50 | 0  |

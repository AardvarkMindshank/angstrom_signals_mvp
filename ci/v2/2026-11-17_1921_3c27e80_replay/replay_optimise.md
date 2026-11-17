# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 208 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.6 | 1.076 | 29.1 | 65.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 62.1 | 1.035 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.5 | 0.809 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.3 | 0.806 | 46.9 | 17.5 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 31.2 | 0.52 | 7.3 | -9.1 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 29.2 | 0.486 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.6 | 0.327 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 19.7 | 0.328 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.8 | 0.213 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.7 | 0.178 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.4 | 0.124 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.4 | 0.123 | 10.8 | 0.0 | 50 | 0  |

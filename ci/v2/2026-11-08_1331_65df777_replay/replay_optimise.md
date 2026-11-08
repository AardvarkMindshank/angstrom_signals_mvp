# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.6 | 1.076 | 29.0 | 64.9 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 61.8 | 1.031 | 32.8 | 23.0 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.8 | 0.814 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 48.6 | 0.811 | 46.9 | 32.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 31.0 | 0.517 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 29.2 | 0.487 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.7 | 0.328 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 19.6 | 0.327 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 12.8 | 0.213 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.6 | 0.176 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.4 | 0.123 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.3 | 0.122 | 10.8 | 0.0 | 50 | 0  |

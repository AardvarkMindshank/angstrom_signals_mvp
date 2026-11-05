# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 92 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 64.4 | 1.073 | 29.0 | 64.4 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 61.1 | 1.019 | 32.8 | 23.0 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 48.1 | 0.801 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 47.9 | 0.799 | 46.9 | 16.1 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 31.2 | 0.52 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 29.5 | 0.492 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 19.9 | 0.332 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 20.1 | 0.335 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 13.2 | 0.22 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 10.7 | 0.178 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 7.3 | 0.122 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 7.3 | 0.122 | 10.8 | 0.0 | 50 | 0  |

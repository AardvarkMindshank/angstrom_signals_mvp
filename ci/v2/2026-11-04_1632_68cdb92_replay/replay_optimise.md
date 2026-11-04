# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 90.0 | 1.501 | 29.0 | 64.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 86.3 | 1.439 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 67.9 | 1.131 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 67.8 | 1.129 | 46.9 | 17.9 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 44.0 | 0.734 | 7.3 | -15.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 41.6 | 0.693 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.9 | 0.464 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 28.0 | 0.466 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.2 | 0.304 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 15.0 | 0.251 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.4 | 0.174 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.3 | 0.172 | 10.8 | 0.0 | 50 | 0  |

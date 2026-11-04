# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 55 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 90.8 | 1.514 | 29.0 | 64.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 87.2 | 1.453 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 68.8 | 1.146 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 68.3 | 1.138 | 46.8 | 18.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.7 | 0.712 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.2 | 0.67 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.4 | 0.456 | 12.5 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.7 | 0.461 | 18.8 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 18.2 | 0.303 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 15.1 | 0.251 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.5 | 0.175 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.4 | 0.174 | 10.8 | 0.0 | 50 | 0  |

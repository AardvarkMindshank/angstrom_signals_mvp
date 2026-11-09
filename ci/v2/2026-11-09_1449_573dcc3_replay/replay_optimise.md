# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 87.5 | 1.458 | 29.0 | 64.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 83.9 | 1.399 | 32.8 | 22.9 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 66.6 | 1.11 | 30.3 | 0.0 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 66.2 | 1.104 | 46.9 | 29.0 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 42.9 | 0.714 | 7.3 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 40.5 | 0.676 | 17.0 | 0.1 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 27.4 | 0.457 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 27.4 | 0.456 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 17.7 | 0.295 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 14.3 | 0.238 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 10.1 | 0.169 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 10.1 | 0.168 | 10.8 | 0.0 | 50 | 0  |

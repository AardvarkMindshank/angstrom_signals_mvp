# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 47.5 | 0.792 | 29.0 | 62.3 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 44.9 | 0.748 | 32.8 | 22.8 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.2 | 0.586 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.0 | 0.584 | 46.9 | 25.2 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 22.3 | 0.371 | 7.3 | -19.8 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.1 | 0.351 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 13.7 | 0.228 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.1 | 0.235 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.2 | 0.153 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.6 | 0.127 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.4 | 0.09 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.3 | 0.088 | 10.8 | 0.0 | 50 | 0  |

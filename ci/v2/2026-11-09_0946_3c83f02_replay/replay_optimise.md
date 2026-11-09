# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 48.8 | 0.814 | 29.0 | 61.8 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 46.0 | 0.767 | 32.8 | 23.0 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 35.1 | 0.586 | 30.3 | 0.2 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 35.7 | 0.595 | 46.9 | 17.7 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 22.5 | 0.375 | 7.3 | -17.9 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 21.3 | 0.355 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 14.4 | 0.241 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 14.4 | 0.239 | 18.9 | 0.0 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 9.5 | 0.159 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 7.7 | 0.129 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.2 | 0.087 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.1 | 0.085 | 10.8 | 0.0 | 50 | 0  |

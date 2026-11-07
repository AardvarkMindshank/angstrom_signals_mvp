# Replay optimisation (stage 5)

Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path.
Slice shortcut allowed for 98 certified signal/timeframe pairs (from the committed certification record).

| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | Steps differing from exact |
|---|---|---|---|---|---|---|---|---|
| synthetic-crypto-s11 | A exact | 60 | 52.0 | 0.866 | 29.0 | 62.1 | 0 | 0  |
| synthetic-crypto-s11 | B reuse frames | 60 | 49.6 | 0.826 | 32.8 | 22.6 | 51 | 0  |
| synthetic-crypto-s11 | C certified slicing | 60 | 39.2 | 0.653 | 30.3 | 0.3 | 0 | 0  |
| synthetic-crypto-s11 | D slicing + reuse | 60 | 38.4 | 0.641 | 46.9 | 26.3 | 51 | 0  |
| synthetic-equity-s23 | A exact | 60 | 25.3 | 0.422 | 7.3 | -32.5 | 0 | 0  |
| synthetic-equity-s23 | B reuse frames | 60 | 24.2 | 0.403 | 17.0 | 0.0 | 48 | 0  |
| synthetic-equity-s23 | C certified slicing | 60 | 15.9 | 0.265 | 12.6 | 0.0 | 0 | 0  |
| synthetic-equity-s23 | D slicing + reuse | 60 | 15.6 | 0.261 | 18.9 | 3.4 | 48 | 0  |
| dev-BTC-USD | A exact | 60 | 10.4 | 0.173 | 5.1 | 0.0 | 0 | 0  |
| dev-BTC-USD | B reuse frames | 60 | 8.5 | 0.142 | 12.1 | 0.1 | 50 | 0  |
| dev-BTC-USD | C certified slicing | 60 | 5.8 | 0.097 | 6.3 | 0.0 | 0 | 0  |
| dev-BTC-USD | D slicing + reuse | 60 | 5.8 | 0.096 | 10.8 | 0.0 | 50 | 0  |

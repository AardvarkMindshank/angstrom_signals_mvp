# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.2 MB
- Importing the card and the Groups/Sets code adds: 6.9 MB
- Growth over all 6 evaluations below: 96.8 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 2.66 | 88.3 |  | 28.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.0 |  | 28.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.29 | 3.4 |  | 28.8 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.55 | 1.2 |  | 27.8 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.58 | 3.5 |  | 28.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.42 | 0.9 | 8.9 | 28.1 | trend: ok, reversal: ok |  |

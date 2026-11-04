# Replay certification (suite v1)

Code hash aa47f1e4aeb1; 8 datasets; at least 50 cutoffs per dataset; 15.0 minutes.

| Signal | Timeframe | Algorithm | Slice shortcut | Cutoffs | Checks (reference/poison/cache/timestamps) | Readings | Reason |
|---|---|---|---|---|---|---|---|
| flows.btc_etf@1 | 1D | certified | no | 70 | 70/70/14/70 | {'ok': 70} | not tested |
| flows.stablecoin_supply@1 | 1D | certified | no | 70 | 70/70/14/70 | {'ok': 70} | not tested |
| levels.zones@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| levels.zones@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| levels.zones@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| levels.zones@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| levels.zones@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 69, 'ok': 265} |  |
| momentum.direction@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| momentum.direction@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| momentum.direction@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| momentum.direction@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| momentum.direction@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 23, 'ok': 311} |  |
| mtf.alignment@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| positioning.liquidation_levels@1 | 1h | not_certified | no | 0 | 0/0/0/0 | {} | Derivatives have no stored history (live only); see decision E. |
| positioning.liquidations@1 | 1h | not_certified | no | 0 | 0/0/0/0 | {} | Derivatives have no stored history (live only); see decision E. |
| positioning.oi_price@1 | 1h | not_certified | no | 0 | 0/0/0/0 | {} | Derivatives have no stored history (live only); see decision E. |
| regime.observation@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| regime.observation@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| regime.observation@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| regime.observation@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| regime.observation@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 69, 'ok': 265} |  |
| regime.state@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| regime.state@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| regime.state@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| regime.state@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| regime.state@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| structure.breaks@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| structure.breaks@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| structure.breaks@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| structure.breaks@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| structure.breaks@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| structure.swings@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| structure.swings@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| structure.swings@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| structure.swings@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| structure.swings@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 24, 'ok': 310} |  |
| ta.divergence.macd@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ta.divergence.macd@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ta.divergence.macd@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| ta.divergence.macd@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| ta.divergence.macd@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 69, 'ok': 265} |  |
| ta.divergence.rsi@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ta.divergence.rsi@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ta.divergence.rsi@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| ta.divergence.rsi@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-AAPL T=2024-02-20T20:59:59+00:00: .value.events[0].indicator_pivots[0].time: 2023-05-15T00:00:00+00:00 vs 2023-05-16T00:00:00+00:00 |
| ta.divergence.rsi@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 69, 'ok': 265} |  |
| trend.direction@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| trend.direction@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| trend.direction@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| trend.direction@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| trend.direction@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 46, 'ok': 288} |  |
| volume.cmf@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.cmf@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.cmf@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| volume.cmf@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| volume.cmf@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| volume.relative@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.relative@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.relative@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| volume.relative@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| volume.relative@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |

Certified: 58 of 61 signal/timeframe pairs.

- synthetic-crypto-s11: 500 days of synthetic 15-minute crypto bars (seed 11), grouped like the chart
- synthetic-equity-s23: 357 sessions of synthetic 15-minute share bars (seed 23), New York hours
- synthetic-etf-flows-s5: synthetic stored ETF flows with first-seen times, next-day revisions and a backfill (seed 5)
- synthetic-stablecoins-s5: synthetic stored stablecoin supply with first-seen times, next-day revisions and a backfill (seed 5)
- dev-BTC-USD: frozen development daily data for BTC-USD, before 2024-10-30
- dev-SOL-USD: frozen development daily data for SOL-USD, before 2024-10-30
- dev-AAPL: frozen development daily data for AAPL, before 2024-10-30
- dev-JPM: frozen development daily data for JPM, before 2024-10-30

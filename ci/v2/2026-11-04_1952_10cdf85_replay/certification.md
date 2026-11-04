# Replay certification (suite v1)

Code hash 793e3cb4a1e6; 12 datasets; at least 50 cutoffs per dataset; 16.1 minutes.

| Signal | Timeframe | Algorithm | Slice shortcut | Cutoffs | Checks (reference/poison/cache/timestamps) | Readings | Reason |
|---|---|---|---|---|---|---|---|
| bollinger.position@1 | 15m | certified | no | 113 | 113/226/46/113 | {'ok': 113} | synthetic-crypto-s11 T=2024-02-04T16:30:00+00:00: .value.standard_score: 0.7347059897980095 vs 0.7347059898057529 |
| bollinger.position@1 | 1h | certified | no | 113 | 113/226/46/113 | {'ok': 113} | synthetic-crypto-s11 T=2024-02-04T17:00:00+00:00: .value.standard_score: 0.6716601608649281 vs 0.6716601608648154 |
| bollinger.position@1 | 4h | certified | no | 112 | 112/224/46/112 | {'ok': 112} | synthetic-crypto-s11 T=2024-06-18T08:00:00+00:00: .value.standard_score: 0.8054676260100697 vs 0.8054676260100726 |
| bollinger.position@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-BTC-USD T=2022-06-28T00:00:00+00:00: .value.standard_score: -0.29304365353360995 vs -0.2930436535336113 |
| bollinger.position@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| flows.btc_etf@1 | 1D | certified | no | 70 | 70/70/14/70 | {'ok': 70} | not tested |
| flows.stablecoin_supply@1 | 1D | certified | no | 70 | 70/70/14/70 | {'ok': 70} | not tested |
| ichimoku.position@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ichimoku.position@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ichimoku.position@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| ichimoku.position@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| ichimoku.position@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| levels.zones@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| levels.zones@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| levels.zones@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| levels.zones@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| levels.zones@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 69, 'ok': 265} |  |
| ma.position@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ma.position@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| ma.position@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| ma.position@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-AAPL T=2020-06-06T12:00:00+00:00: .value.standard_score: 0.8812938185869703 vs 0.8812938185869704 |
| ma.position@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 46, 'ok': 288} |  |
| macd.acceleration@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| macd.acceleration@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| macd.acceleration@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| macd.acceleration@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-AAPL T=2020-06-06T12:00:00+00:00: .value.standard_score: -0.09698210308148068 vs -0.0969821030814807 |
| macd.acceleration@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 7, 'ok': 327} |  |
| macd.level@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| macd.level@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| macd.level@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| macd.level@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| macd.level@1 | 1W | certified | no | 334 | 334/668/136/334 | {'insufficient_data': 7, 'ok': 327} | synthetic-crypto-s11 T=2023-10-02T00:00:00+00:00: .available_at: 2023-10-02T00:00:00+00:00 vs None |
| momentum.direction@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| momentum.direction@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| momentum.direction@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| momentum.direction@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| momentum.direction@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'insufficient_data': 23, 'ok': 311} |  |
| move.seven_day@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| move.seven_day@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| move.seven_day@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| move.seven_day@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| move.seven_day@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| mtf.alignment@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| obv.balance@1 | 15m | certified | no | 113 | 113/226/46/113 | {'ok': 113} | synthetic-crypto-s11 T=2024-02-04T16:30:00+00:00: .value.obv: 147799.641284 vs 103652.64973 |
| obv.balance@1 | 1h | certified | no | 113 | 113/226/46/113 | {'ok': 113} | synthetic-crypto-s11 T=2024-02-04T17:00:00+00:00: .value.obv: 369253.168341 vs 750237.999617 |
| obv.balance@1 | 4h | certified | no | 112 | 112/224/46/112 | {'ok': 112} | synthetic-crypto-s11 T=2024-06-18T08:00:00+00:00: .value.obv: 853083.665237 vs 328620.328287 |
| obv.balance@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-BTC-USD T=2022-06-28T00:00:00+00:00: .value.obv: 1686400486036.0 vs 510955557787.0 |
| obv.balance@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
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
| rsi.level@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| rsi.level@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| rsi.level@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| rsi.level@1 | 1D | certified | no | 342 | 342/684/142/342 | {'ok': 342} | dev-AAPL T=2024-09-23T20:00:00+00:00: .value.standard_score: 0.20193662997585282 vs 0.20193662997585235 |
| rsi.level@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| sentiment.asset@1 | 1D | certified | no | 140 | 140/140/28/140 | {'ok': 138, 'stale': 2} | not tested |
| sentiment.market@1 | 1D | certified | no | 140 | 140/140/28/140 | {'ok': 138, 'stale': 2} | not tested |
| stochastic.level@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| stochastic.level@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| stochastic.level@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| stochastic.level@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| stochastic.level@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
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
| volume.heavy_candle@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.heavy_candle@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.heavy_candle@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| volume.heavy_candle@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| volume.heavy_candle@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |
| volume.relative@1 | 15m | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.relative@1 | 1h | certified | yes | 113 | 113/226/46/113 | {'ok': 113} |  |
| volume.relative@1 | 4h | certified | yes | 112 | 112/224/46/112 | {'ok': 112} |  |
| volume.relative@1 | 1D | certified | yes | 342 | 342/684/142/342 | {'ok': 342} |  |
| volume.relative@1 | 1W | certified | yes | 334 | 334/668/136/334 | {'ok': 334} |  |

Certified: 110 of 113 signal/timeframe pairs.

- synthetic-crypto-s11: 500 days of synthetic 15-minute crypto bars (seed 11), grouped like the chart
- synthetic-equity-s23: 357 sessions of synthetic 15-minute share bars (seed 23), New York hours
- synthetic-etf-flows-s5: synthetic stored ETF flows with first-seen times, next-day revisions and a backfill (seed 5)
- synthetic-stablecoins-s5: synthetic stored stablecoin supply with first-seen times, next-day revisions and a backfill (seed 5)
- synthetic-sentiment-market-crypto: synthetic stored sentiment, twice daily with gaps and thin-news days (seed 9)
- synthetic-sentiment-market-stocks: synthetic stored sentiment, twice daily with gaps and thin-news days (seed 9)
- synthetic-sentiment-crypto-synthetic-coin: synthetic stored sentiment, twice daily with gaps and thin-news days (seed 9)
- synthetic-sentiment-equity-SYNTH: synthetic stored sentiment, twice daily with gaps and thin-news days (seed 9)
- dev-BTC-USD: frozen development daily data for BTC-USD, before 2024-10-30
- dev-SOL-USD: frozen development daily data for SOL-USD, before 2024-10-30
- dev-AAPL: frozen development daily data for AAPL, before 2024-10-30
- dev-JPM: frozen development daily data for JPM, before 2024-10-30

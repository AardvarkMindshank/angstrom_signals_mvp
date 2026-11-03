# Angstrom Signal Library (v3 foundation)

Status: development only. Not shown to users; does not change Trend, Stretch, Flow, alerts, evidence or any setting.
Admins can inspect every signal in the app under **🧪 Signal Library (development)** (runs only when *Evaluate* is pressed).

Guiding principle: every score explainable, every signal inspectable, every grouping customizable.

## 1. Architecture

```
Data Sources ──► Signal Library ──► Signal Groups ──► Signal Sets ──► Workspace / Strategies
(chart_data,      (this package)     (not built)       (not built)      (not built)
 Supabase rows)
```

| Piece | File | Responsibility |
|---|---|---|
| Definitions, references, results, registry | `signal_library/core.py` | What a signal is; immutable versions |
| Data access | `signal_library/context.py`, `loaders.py` | Loads each input once per pass; signals never fetch |
| Evaluation | `signal_library/engine.py` | De-duplication, data-keyed cache, error isolation |
| Pure calculations | `signal_library/swings.py` | Swing points, divergences, structure, zones (array maths, no look-ahead) |
| Signal definitions | `signals_basic.py`, `signals_ta.py`, `signals_market.py` | Metadata + compute functions |
| Development view | `signal_inspector.py` | Admin-only inspector and catalogue |

**Signal definition** (`SignalDefinition`): stable dotted `id`, integer `version`, name, category, output type,
native unit, scope (any asset / crypto only / one market), supported timeframes, required data, calculation,
interpretation, limitations, parameters with conventional defaults, and `evidence_strength` (all are
`descriptive`; `researched` is reserved for signals with out-of-sample evidence). A changed calculation gets a new
version; old versions stay registered so pinned references keep working.

**Signal reference** (`SignalRef`): `id`, pinned `version`, `timeframe`, `params`. No asset: the same reference
works on any asset. It is plain JSON and hashes to a stable `instance_key`. This is what Groups will store.

**Signal result** (`SignalResult`): status (`ok`, `insufficient_data`, `missing_data`, `stale`, `unsupported`,
`error`), confirmation (`confirmed` / `developing`), the native value, unit, `observed_at` (what the value describes),
`available_at` (when it could first be known: candle close, or the first time Angstrom saw a published value),
`backfilled`, evidence, provenance and plain-language notes.

**Output types**: numeric, direction, boolean, category, events, levels, observation. Nothing is forced onto
−100..+100; turning a value into a contribution is a Group's job and must be explicit there.

**Caching**: results are cached in process (512 entries, 15 minutes) keyed by reference + subject + a fingerprint
of the input data (last candle time and close, or the derivatives record time), so a new candle refreshes them.
Candles are also cached by `chart_data` (60–300 s, shared by all sessions). Nothing new is stored in Supabase
(decision: calculate on demand).

**No look-ahead**: candle signals use closed candles only; swing points are confirmed `right` candles later;
structure breaks are judged with only the swings confirmed before that candle. Tests recompute divergences and
structure breaks on data cut at each confirmation and require identical results.

## 2. Signal catalogue

See `docs/signal_library_catalogue.md` (generated from the registry, so it always matches the code). 17 signals:

| Area | Signals |
|---|---|
| Multi-timeframe | `trend.direction@1`, `momentum.direction@1`, `mtf.alignment@1` (per-timeframe table, counts, conflicts, momentum-against-trend; no score) |
| Divergences | `ta.divergence.rsi@1`, `ta.divergence.macd@1` (regular and hidden, bullish and bearish; confirmed, developing, invalidated, expired) |
| Structure and levels | `structure.swings@1` (HH/HL/LH/LL, tentative swings), `structure.breaks@1` (BOS / potential CHoCH), `levels.zones@1` (support/resistance zones with distance and retests) |
| Regime | `regime.state@1` (existing rules unchanged), `regime.observation@1` (ADX and its change, efficiency ratio, ATR% and band-width percentiles, compression/expansion, in-transition flag) |
| Volume | `volume.cmf@1`, `volume.relative@1` |
| Capital flows | `flows.btc_etf@1` (latest, 5- and 20-session sums, acceleration, per fund), `flows.stablecoin_supply@1` (7/30-day change, acceleration) |
| Positioning (crypto) | `positioning.oi_price@1` (OI and price change, inferred build-up/unwinding, funding, long/short), `positioning.liquidations@1`, `positioning.liquidation_levels@1` (estimates) |

Reused, not rebuilt: indicator columns from `scoring.calculate_indicators`; candles from `chart_data` (the chart's
15m–1W candles, sessions and forming flag); regime rules from `regime.py`; derivatives from the stored Coinalyze
record; flows from `capital_flow_observations`. New formulas only where none existed: swing points and what is built on
them, Kaufman efficiency ratio, band-width percentile, CMF.

## 3. Data dependencies

| Data | Source | History | Freshness | Licence / terms notes |
|---|---|---|---|---|
| Candles 15m / 1h (4h) / 1D / 1W | Yahoo Finance via `yfinance` | 15m ≈ 60 days; 1h ≈ 2 years; daily/weekly full | 1–5 min cache | Yahoo's terms are for personal use; a commercial launch needs a licensed price feed (see roadmap) |
| Indicators | `scoring.calculate_indicators` (pandas-ta) | — | per candle | MIT |
| Derivatives | Coinalyze (stored hourly by the worker) | 7 days hourly | ≈ hourly; stale after 3 h | free API key; check commercial terms before launch |
| Liquidation levels | Angstrom estimate from Coinalyze open interest | 7 days | ≈ hourly | estimate, labelled as such |
| BTC ETF flows | TFTC tracker (stored) | since 2024-01-11 | daily, ≥1 session late, revisable | CC BY 4.0, attribution shown |
| Stablecoin supply | DefiLlama (stored) | full | daily | see `capital_flows.SOURCES` |

Backfilled flow history is flagged; `point_in_time=True` drops it for research replays.

## 4. Validation

- **Correctness**: hand-built examples for swing points, all four divergence types, invalidation, expiry,
  developing candidates, HH/HL labels, CHoCH, zone clustering, chained-zone width cap, retests, CMF, efficiency ratio,
  ETF sums with revisions and backfill, stablecoin changes, open-interest readings, liquidation sums and levels.
- **No look-ahead / repainting**: truncation tests for divergences and structure breaks; every candle signal is
  checked to ignore an absurd forming candle.
- **Live data**: `signal_library_live.py` runs every candle signal on 15m–1W Yahoo candles for BTC, ETH, AAPL and
  SPY in CI (224 evaluations, 0 errors).
- **Redundancy (development data only, before the hold-out; no forward returns)**, `signal_library_check.py`:

| | Stocks (61) | Crypto (25) |
|---|---|---|
| Trend vs momentum agree, when both directional | 84% | 81% |
| Trend vs swing structure agree | 80% | 79% |
| Momentum vs swing structure agree | 53% | 57% |
| Efficiency ratio vs ADX (Spearman) | 0.46 | 0.44 |
| Efficiency ratio vs strength of the Trend reading | 0.58 | 0.54 |
| Divergences per 1,000 daily candles (each type) | 4–14 | 5–12 |
| Share invalidated within 30 candles | 45–67% | 46–57% |
| Zones per asset (median) / width | 4 / 1.3% | 4 / 2.0% |

  Reading: trend and momentum direction mostly repeat each other (same price inputs), so a Group should not count both
  as independent confirmation; swing structure adds the most distinct view. Roughly half of all divergences fail
  within 30 candles, so a divergence alone is weak evidence. None of this is predictive testing.
- **Regression**: full suite 522 passed in CI (with pandas-ta and Streamlit), including the inspector run inside
  Streamlit's test harness. Existing readings, alerts and settings are untouched (no imports from the library in
  scoring, alerts, evidence or the worker).

## 5. Resource impact

- **Database**: no new tables or columns. Per inspection: one `asset_market` read and three
  `capital_flow_observations` selects (≈120 days).
- **API**: only when an admin presses *Evaluate*: up to 4 Yahoo requests per asset (15m, 1h shared by 4h, 1D, 1W),
  cached 1–5 minutes and shared. No extra Coinalyze, TFTC or DefiLlama calls (stored data only).
- **Memory**: about 1 MB per loaded timeframe (≤ 4,000 candles × ~40 columns), freed after the run; result cache
  bounded at 512 entries (well under 10 MB).
- **CPU**: swing, divergence, structure and zone calculations take 6–8 ms per year of daily candles; a full
  inspection of one asset (17 signals, 5 timeframes, including candle fetches) takes about 1–5 s, mostly the
  Yahoo fetch and the indicator pass.

## 6. Roadmap: valuable signals that need data or research

| Priority | Opportunity | Measures | Provider options | Licence / cost | Distinct? |
|---|---|---|---|---|---|
| 1 | Anchored VWAP and volume profile | Value areas, volume nodes, VWAP from swing anchors | Existing Yahoo candles (bar-level approximation) | No new cost | Yes: adds volume-at-price to the zones |
| 2 | Cross-market relative strength and risk context | RS vs S&P 500 / BTC, VIX, dollar, yields | Existing Yahoo data; FRED for rates | Free (FRED mostly public domain) | Partly (RS overlaps Trend in the audit) |
| 3 | Insider transactions | Form 4 buys/sells, clusters | SEC EDGAR (free); Finnhub (key already held) | EDGAR public; check Finnhub terms | Yes |
| 4 | Institutional ownership changes | 13F holder changes | SEC EDGAR 13F | Public; 45-day lag, quarterly | Yes, slow |
| 5 | Crypto exchange in/outflows; stablecoins to exchanges | Coins moving to/from exchanges | CryptoQuant, Glassnode, Coin Metrics | Paid tiers; redistribution usually restricted (prices not checked) | Yes |
| 6 | Full liquidation heatmaps | Order-book and leverage-based liquidation maps | CoinGlass API, Hyblock | Paid; display terms vary (prices not checked) | Yes, beyond our estimate |
| 7 | Better options positioning | Dealer gamma, skew, flows | ORATS, Polygon options, Cboe DataShop; Deribit (crypto, free public API) | Paid for equities; Yahoo chains are personal-use | Yes |
| 8 | Equity ETF flows | Sector/asset ETF creations and redemptions | Issuer files, ETF.com/FactSet | Mostly paid | Yes |
| — | Licensed intraday prices | Replace Yahoo for commercial use | Polygon/Massive, Tiingo, Alpaca, exchange feeds | Paid | Needed before launch |

## 7. Groups / Sets readiness: decisions still needed

1. **Where Groups and Sets live.** Recommended: two new tables (owner, visibility private/public/community,
   version, parent copy id, JSON config of `SignalRef`s, weights, roles), so sharing, attribution and row-level
   security work. Alternative: JSON in `user_preferences` (simpler, but hard to share).
2. **Normalisation rules.** How native values become contributions (direction maps, thresholds, percentiles,
   z-scores), versioned like signals. Proposed: a small transform registry owned by the Groups layer.
3. **Rules vs weights.** Semantics for AND/OR, confirmations and vetoes, and how missing or stale members count
   (ignore, fail, or neutral).
4. **History.** Group alerts, redundancy diagnostics on live data and backtests need stored signal history; this
   reverses today's "calculate on demand" decision for whatever Groups use.
5. **Intraday breadth.** Running intraday Groups across whole watchlists needs the worker plus many Yahoo calls, or
   a paid intraday feed.
6. **Version upgrades.** When a signal gets v2, pinned Groups keep v1; decide how users are offered the upgrade.
7. **Non-US equity sessions.** Sessions come from Yahoo metadata; confirm the markets we support.

Recommended next step: build the Groups data model and a read-only Group evaluator (no UI), with two starter Groups
(Trend Confirmation, Reversal Evidence) defined as JSON, plus redundancy diagnostics using this library's outputs.

# Signals v2: ready for review (branch v2, not merged, not deployed)

## What changed
- Engine: signals_v2.py (version 2.0.0, definition fingerprint in every result). Three descriptive readings,
  -100..+100, positive = up: Trend (50/200 MAs, Ichimoku, MACD line), Stretch (RSI, Stochastic, Bollinger,
  7-day move, MACD histogram), Flow (OBV, heavy-volume day). Context (ATR%, ADX, regime, volume) never directional.
  Two named views (trend-following, mean-reversion) carry the hypotheses. Finished daily bars only; missing data is
  missing, never neutral; smooth mappings, no cliffs. No 0-100 score anywhere.
- App: Trend/Stretch/Flow columns, snapshot cards by Trend, asset card with evidence badges, Signals Breakdown,
  What changed on Trend, Trend alert line slider, Help rewritten. v1 weights, presets, adaptive switch removed.
- Alerts worker, digest, signal matrix and per-asset evidence (record version 2) all use v2. v1 thresholds,
  snapshots and evidence records are ignored, so nothing v1 acts on v2 numbers.
- v1 stays reproducible through Git and the research records (scoring.compute_score, backtest.py, research.py kept).

## Checks
- Local: 301 passed, 6 skipped (need pandas-ta). GitHub (7ba0e9c): 341 passed; v2_smoke.py end-to-end check PASS
  (6 real assets, development rows only; 0.05 s per asset, peak 307 MB).
- Overlap on current definitions (development data): no saturated components; pullback/rally note on ~5% of days;
  Trend-Stretch 0.57-0.59.

## Known limitations
- Stretch and Flow overlap (0.73-0.78 correlation): OBV vs its 20-day average behaves like recent momentum.
- Heavy-volume component is zero on ~75% of days (by design: it only reacts to heavy days).
- None of the directional readings or views is validated; only stock ATR% (move size) carries a "tested" badge.
- The Streamlit app itself has not been run by Claude (no Supabase login in the build environment).

## Deployment notes
- No database changes: the Trend alert line is saved in user_preferences.settings (trend_alert_level, default 50).
- Old min/max score alert columns and scoring_weights are left in the database, unused.
- Per-asset evidence rebuilds automatically (v1 records are hidden until rebuilt, ~2 assets per worker run).
- Merging to main redeploys Render and switches the alerts worker to Trend alerts.

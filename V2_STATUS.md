# Signals v2: work in progress (branch v2, not merged, not deployed)

Done in this commit:
- app.py integrated with signals_v2 / signals_view: watchlist rows (Trend/Stretch/Flow columns), snapshot cards,
  asset card, Signals Breakdown, What changed (Trend, +/- alert line), Trend alert line slider
  (settings.trend_alert_level), Help text; v1 weights sliders, presets, adaptive switch and score popover removed.
- signal_matrix.py replays v2 readings (Trend, Stretch, Flow, two named views); evidence.py record VERSION 2
  tests the Trend reading, v1 records hidden and rebuilt; digest drops v1 thresholds.
- New tests: tests/test_signals_view.py, matrix and evidence additions. New v2_smoke.py end-to-end check in CI.

Unfinished / to check next session:
- Full local test suite was not re-run after the last edits (interrupted); read CI results in reports/ci/v2/.
- v2_smoke.py has never run yet (needs pandas-ta: runs in the v2-checks overlap job).
- Overlap re-run on current definitions (previous run crashed on a renamed key; fixed in v2_overlap.py).
- No live Streamlit check yet: run the branch locally or against the angstrom-test Supabase project.
- New accounts still get default v1 scoring_weights written (harmless, unused); consider dropping.
- Then: final summary of changes, limitations and deployment notes for approval.

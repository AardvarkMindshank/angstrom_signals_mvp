# Lattice stage 6 report: Trend, Stretch and Flow come from the starter Groups everywhere

Branch `lattice-stage6`, 5 November 2026. Agreed with the owner after stage 5 (option a): keep the same three
readings across the app, but have the starter Groups produce them, so what users see on the dashboard is the
same thing they can open, copy and change in Lattice.

## What changed

- **`group_readings.py`** (new): `score(frame, kind)` returns the same shape as the old scorer, so every screen
  keeps working. Trend, Stretch and Flow are evaluated by the starter Groups on the same stored daily bars (the
  last finished bar, as before). Each reading now also carries its Group: name, outcome, status and data
  completeness (Complete / Partial / None).
- **Labels are Group outcomes**: five bands per reading, the same edges as before (strong ±0.5, band ±0.2), written
  as ordered outcome rules. Trend and Stretch wording is unchanged. Flow is shortened to fit the 24-character label
  limit: "Strong buying volume", "Buying volume", "Volume neutral", "Selling volume", "Strong selling volume".
- **Switched to the Groups:** the watchlist tables and asset card (`signals_view.row_fields`, `app.py`), the
  breakdown, the signal matrix (`signal_matrix.py`), the alert and digest worker (`run_alerts.py`), the
  return-visit snapshot, and the smoke check (`v2_smoke.py`).
- **On the card**: a 🧩 icon beside each reading (🧩◐ when some parts had no data), with a hover note naming the
  Group and how many parts had data. The explainer says the readings come from the starter Groups and points to
  Lattice.

## What did not change

- **The numbers.** The starter Groups were built to reproduce the old calculation, and CI already checks it on real
  indicators and development data (`replay_certify.py --parity`). The new tests compare every reading, part,
  label band, view and context field at many cutoffs on synthetic crypto and share data: identical.
- **Alerts.** Trend alerts fire on the same numbers, so the switch cannot set off a burst of alerts and no reset of
  the alert latches is needed. Thresholds and re-arm distance are unchanged.
- **Context** (volatility, trend strength, regime, warnings) and the two named views still come from the existing
  calculation: no Group describes them yet.
- **Research records** (`evidence.py`, validation and overlap reports) keep the old scorer and its definitions
  reference, so past research stays reproducible. The old module stays for that and for the context above.
- Prism's own labelled demo Groups (Bullish / Neutral / Bearish at ±0.3) are unchanged; they are separate
  documents for scanning.

## Cost

Three Group evaluations per asset add a few milliseconds (about 5 ms for the three on 420 daily bars locally); the
row cache key now uses the Groups' definitions reference, so cached rows refresh once after the deploy.

## Tests and checks

- `tests/test_group_readings.py`: identical numbers, parts, coverage, bands, views and context at many cutoffs; the
  band edges (+0.5, +0.2, -0.2, -0.5) match the old wording; the dashboard Groups validate and their labels fit;
  no-data messages unchanged; the app, the worker, the matrix and the row builder no longer call the old scorer.
- Full local suite: **792 passed, 15 skipped, 0 failed**.

## CI

To be reported before merge approval.

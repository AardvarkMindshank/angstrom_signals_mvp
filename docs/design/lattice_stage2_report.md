# Lattice stage 2 report: Prism · Run now (admin preview)

Branch `lattice-stage2`, 5 November 2026. Design: `docs/design/lattice_prism.md` §5.1 and §8 stage 2. Admin only:
nothing changes for other accounts, the dashboard, Trend/Stretch/Flow, alerts, the Signal Matrix or saved
configurations. No SQL.

## What was built

| Part | File | What it does |
|---|---|---|
| Run now | `prism.py` | Runs a Set with a decision on up to 40 assets, **now** (live, confirmed candles) or at **one past moment** (display reconstruction, one replay step for every asset). One row per asset: each decision line's reading (✓ / ✗ / ?), the answer, how sure (Definite / Undecided), the decisive reason in plain words, and data available. Refuses a Set without a decision, an invalid Set, or more than 40 assets. A refused reconstruction is reported for that asset only. |
| Demo Sets | `prism.py` | The starters have no outcome labels, so two admin demos are built in code from copies of the starters with labels added: **Trend and Flow agree** and **Trend up, not overstretched** (Trend bullish, Stretch not stretched up, asset sentiment ≥ −20). The starters themselves are unchanged (tested). |
| Screen | `prism_view.py`, `signal_inspector.py` | A **🔎 Prism** tab in the admin 🧪 Signal Library panel: Set picker (demos and any readable saved Set with a decision), assets (default: the Watchlist), Now or a past moment, **Run now**. Summary line (Yes / No / Unknown counts), results sorted Yes, Unknown, No, with hover help on Answer, How sure and Data available. Past moments carry the reconstruction notice. Nothing is saved or exported. |

## Reasons, as shown

- Yes: "Every line holds."
- No: "Fails on trend outcome is bullish (reading: neutral). Missing Asset sentiment could not change this."
- Unknown: "Depends on mood.score ≥ -20, which could not be decided."

## Tests

`tests/test_prism.py`, 7 tests:
- demo Sets valid and scannable; starters untouched;
- one row per asset, outcome consistent with the Group score, table columns;
- missing sentiment gives Unknown (Partial) or a definite No that says the gap could not change it, never a guess;
- reason wording; refused Sets and asset limit; a refused reconstruction for one asset;
- the tab runs inside Streamlit, produces the table and offers no download (runs in CI; Streamlit is not
  installable in the build sandbox).

Full local suite: **724 passed, 13 skipped, 0 failed**.

## Not in this stage

Scheduled scans and alerts (stage 3), the editor (stage 4), E4, History, strategies. Prism is a tab in the admin
panel for now; it becomes the Lattice page when the editor exists.

## CI

Run 42033659768 on commit 6ef380d (pushed to `v2`): **all four jobs passed** (tests 776 passed including the
Prism tab inside Streamlit, chart, overlap, replay with certification `--check`, Trend/Stretch/Flow parity and
shortcut comparison).

This branch also carries the last part of the approved certification fix (`point_in_time.md` §13): `--check` keeps
the `slice_reason` text informational, because for a pair that is genuinely not equivalent two machines can report a
different first field. Equivalence and every certification result are still compared (`tests/test_cert_check.py`).

## For merge approval

Merging adds the 🔎 Prism tab to the admin Signal Library panel only. Nothing changes for other accounts.

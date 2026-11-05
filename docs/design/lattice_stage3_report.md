# Lattice stage 3 report: Prism scheduled scans and alerts (admin preview)

Branch `lattice-stage3`, 5 November 2026. Design: `docs/design/lattice_prism.md` §5.2–5.3 and §8 stage 3. While
Prism is in preview only admin accounts can save scans (enforced by the database). Nothing changes for other
accounts, the dashboard, Trend/Stretch/Flow, existing alerts or the Signal Matrix. Needs one SQL file run once.

## What was built

| Part | File | What it does |
|---|---|---|
| Storage | `sql/2026-11-06_prism_scans.sql` | `prism_scans` (a pinned copy of a Set with its decision, schedule, alert mode, email on/off, paused), `prism_scan_runs` (one row per scan, market and cutoff: the claim, results, opened/released alerts, replay record, error) and `prism_scan_latches`. Owners read their own rows; all writes go through three security-definer functions (`prism_save_scan`, `prism_delete_scan`, `prism_reset_latches`). At most 5 active scans per account; admins only while in preview. Re-runnable. |
| Schedules | `prism_scans.py` | Each 4-hour, daily or weekly close, or up to 4 set times a day in a chosen time zone (every day, weekdays or chosen days). The cutoff T is the candle's close, counted 10 minutes after it so the provider has the closed candle; set times use the time itself. Crypto and shares are separate runs: shares close at 16:00 New York on weekdays (the library's share calendar), and a 4-hour scan checks shares at their daily close. A warning, never a block, when a scan runs faster than any of its members can change. |
| Worker | `prism_scans.py`, `run_alerts.py` | Runs inside the existing 5-minute worker **after** all existing alert and digest work, in at most 4 minutes. Due runs are claimed once by the unique (scan, market, cutoff) row; evaluated at T through the point-in-time reconstruction; results and the replay record stored. Oldest cutoff first; runs that do not fit wait for the next pass and record how late they ran. A failure is recorded for that scan only. Stale claims expire after 30 minutes; runs are kept 90 days. Missed cutoffs are not back-filled. If the tables are not installed the worker says so and carries on. |
| Alerts | `prism_scans.py` | Latch per (scan, asset): the first Yes ever seen alerts once; only a confirmed No releases it; Unknown and failed runs neither open nor release it. Optional "every run while Yes". In-app notification (type `prism`, linked to the asset like other alerts), instant email when the owner has instant alerts on, otherwise the daily summary. |
| Digest | `digest.py` | A **Prism scans** section in the daily summary on days with Prism matches. With none, the summary is byte-for-byte what it was (tested). |
| Screen | `prism_view.py` | The 🔎 Prism tab gains **⏰ Scheduled scans**: list of your scans, a plain form (name, Set, schedule, alert mode, email), Pause/Resume, Reset alerts, Delete, and the latest run grouped as New Yes · Still Yes · Couldn't decide · No, labelled as the stored record. |

## Tests

`tests/test_prism_scans.py`, 26 tests:
- cutoffs for every timeframe and market, including the settle time, summer and winter New York time, weekends,
  weekly closes, and set times with zones and days; schedule validation and wording; the faster-schedule warning;
- the alert truth table, and over five runs: first Yes alerts once, Unknown keeps the latch, a No releases it, the
  next Yes alerts again; a cutoff runs once even when the worker runs twice; "every run" mode;
- failure isolation, the time budget, instant email following the alert settings and the scan's email switch;
- crypto and shares as separate runs at their own closes; grouping for the page;
- the digest section appears only with Prism notes; the SQL is re-runnable, owner-only and claims once; the
  Scheduled scans view renders inside Streamlit (in CI).

Existing digest and alert tests pass unchanged.

## To switch it on

1. Run `sql/2026-11-06_prism_scans.sql` once in the Supabase SQL editor.
2. In 🧪 Signal Library → 🔎 Prism → ⏰ Scheduled scans, save a scan (for example "Trend and Flow agree", each daily
   close). It runs after the next close plus 10 minutes, on the next worker pass.

## Not in this stage

Opening Prism to all accounts (a small SQL change and moving the tab), Discord and Telegram, assets outside the
Watchlist, History, the editor, strategies.

## CI

Run 42039495267 on commit 5a37677 (pushed to `v2`): **all four jobs passed** (tests including the Scheduled scans
view inside Streamlit, chart, overlap, replay with certification `--check`).

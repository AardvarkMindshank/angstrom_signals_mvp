# Lattice stage 7 report: Prism Scans as saved objects, and faster editing

Branch `prism-scans`, 6 November 2026. Built from the agreed mockup (Prism Scans, desktop and iPhone) and the
owner's follow-up on alerts. Needs one SQL file: `sql/2026-11-08_prism_scan_objects.sql`.

## 1. The Prism Scan page is a board

- **Left:** saved Sets (newest scannable version of each, plus the example Sets) and the Watchlist, each with a
  filter. Watchlist groups (Whole Watchlist, All crypto, All shares) follow the Watchlist as it changes; single
  assets stay fixed. Drag, or tap + (iPhone).
- **Right:** the account's **Prism Scans**. Dropping a Set (or tapping +) saves a new scan straight away: whole
  Watchlist, runs only when Play is pressed, instant alerts.
- **Each scan is a collapsible card.** Collapsed: name, Set version, "vN available" and Paused badges, Yes / No / ?
  counts from the last scheduled run, a dot for each of the last 10 runs, time to the next run, and the controls:
  ▶ run now, ⏪ past moment, ⏸ pause / ▶ resume, duplicate, ✕ delete (press twice). Expanded: assets (remove with
  ×), when it runs, alerts, "Yes now" with snooze, snoozed assets, and the latest results with each deciding line.
  **Expand all / Collapse all** at the top. Which cards are open is remembered while the page is open.
- The old Run now form and Scheduled scans form are replaced by the board.

## 2. What each scan keeps

| Setting | Choices |
|---|---|
| Assets | Watchlist groups and fixed assets, 1 to 60 entries |
| Runs | Only when I press Play · each 4-hour, daily or weekly close · at set times (time zone, days) |
| Alerts | Instant (app and email) · Daily digest · App only · Off |
| Alert when | Turns Yes (default on) · Turns No · Can't run (a failed run, or at least half the answers Unknown) |
| Snooze | one asset on one scan for 1, 3 or 7 days |
| Set version | pinned; "vN available" switches to the newer saved version in one tap |

- **Limits:** at most 5 *scheduled* scans; paused and Play-only scans don't count. ▶ checks up to 40 assets, one
  run every 20 seconds.
- **Resume quietly:** the first run after resuming records the answers and latches without alerting, so resuming
  never sends a burst.
- **Duplicate** copies the scan as Play-only, so a copy never pushes past the limit.
- **Older scans** (saved before this stage) keep their old alert behaviour (the account's instant setting) until an
  alert setting is changed on the board.

## 3. The background worker

`prism_scans.py`: each scan reads its own assets (`scan_assets`); Play-only scans never run on schedule; alerts
follow the scan's channel and ticks; snoozed assets update their latch but don't alert; Instant and App-only notes are
kept out of the daily digest; Daily-digest notes go only to the digest; Off records results and latches only.

## 4. Faster editing (owner's report from iPhone)

Adding or changing anything in the Group and Set editors made the whole dashboard reload, sometimes twice.

- **The change shows at once.** The editors draw an edit in the browser immediately; Python's checks and
  description follow.
- **Only Angstrom Lattice reloads.** The section runs as a Streamlit fragment: changes inside it no longer rerun the
  dashboard.
- **One reload, not two.** The browser's change is read before the editor is drawn, so the second rerun is gone. The
  same applies to the Prism board's buttons.

## 5. SQL

`sql/2026-11-08_prism_scan_objects.sql`, safe to run more than once: adds `assets`, `snoozes` and `quiet_next` to
`prism_scans`, allows the `manual` schedule, and adds `prism_put_scan(p_id, p_scan)` (owner only, checks every field
and the 5-scheduled limit, sets `quiet_next` when a paused scan is resumed). Nothing is removed. Until it is run, the
board shows its library and existing scans, and any change says the update is needed.

## Tests and checks

- `tests/test_prism_board.py`, 13 tests: library lists, card summary and details, next run, asset edits, snoozes,
  duplicates, older alert settings, schedule and alert settings, every board action through `prism_put_scan`, Play
  with its cooldown and size limit, per-scan assets, every alert channel, Turns No, Can't run, snooze, quiet resume,
  older scans, the SQL, and the one-reload editing.
- **Browser, Prism board (new, 28 checks):** collapsed summaries, dots, Expand / Collapse all, arrows, + and drag
  for Sets, assets and groups, ▶, ⏪ with date and time, pause and resume, two-press delete, alert channel and
  ticks, schedule with set times, snooze, version update, both filters, iPhone width with thumb-sized buttons.
- **Browser, Group editor:** a new check that an added signal shows at once, before Python answers.
- **Inside Streamlit:** the Prism board appears styled; tapping + saves a scan that comes back as a card; pause is
  saved and shown; no sideways scrolling at iPhone width.
- Full local suite: **807 passed, 14 skipped, 0 failed**.

## CI

To be reported before merge.

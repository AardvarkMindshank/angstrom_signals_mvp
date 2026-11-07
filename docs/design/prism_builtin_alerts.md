# Built-in alerts in Prism

**Status:** built (November 2026). Code: `builtin_alerts.py`; database: `sql/2026-11-10_prism_builtin_alerts.sql`.

## What changed

The Trend, Stretch and Flow alerts used to be checked by the background worker every 5 minutes, for every account,
outside Prism. They are now six **built-in Prism scans** per account: *Trend turns up*, *Trend turns down*, and the
same for Stretch and Flow. One alert system, one set of rules.

| | Before | Now |
| --- | --- | --- |
| When | every 5 minutes | once at each daily close: crypto 00:10 UTC, shares 10 minutes after the New York close |
| What is read | the starter Groups on the stored daily bars | the same: a Set over the starter Group, on the same stored bars, so the numbers match the dashboard exactly |
| Line and on/off | Notifications → Configure Alert Rules | unchanged: the worker keeps the six scans in step with those settings |
| Repeat after a wobble | re-arms 20 points back through the line | unchanged, as the scan's **re-arm** Set ("Trend at most +30") |
| Words, feed, emails, digest | Trend turned up: +62 … | unchanged (same alert types and messages) |
| Switching one on | current positions recorded quietly | unchanged (the scan's first run is quiet) |

The readings only change when a daily bar closes, so checking every 5 minutes found nothing new between closes.

## Rules

- The built-in scans run on the whole Watchlist (hidden markets left out), at each daily close, and can't be paused
  or deleted: setting their alerts to Off stops them running. They don't count towards the 5 scheduled scans.
- A run waits until the closed bar has reached the stored prices (at most 2 hours after the close).
- Each run is claimed once per scan, market and close, as with every Prism scan.
- Each asset's stored bars become an engine context once per worker pass, shared by every account.
- The readings for the daily digest's watchlist summary are worked out only when that digest is due.

## Re-arm for every scan

Any Prism scan can now carry a **re-arm** Set: an asset that has alerted alerts again only after the re-arm Set says
Yes for it, instead of after any No. The built-in scans use it; choosing one for your own scans comes with the next
display changes.

## Switch-over

On its first pass after the SQL is run, the worker creates each account's six scans from its alert settings and
copies every open (or cleared but still latched) Trend, Stretch and Flow alert into the new scans' latches, so
nothing alerts twice. The first run of each scan is quiet. Market sentiment alerts are unchanged.

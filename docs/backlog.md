# Backlog

Agreed work that is not built yet, so nothing gets forgotten between sessions. Newest first.

## Tides

- **Monthly macro-calendar check** (agreed 12 Nov 2026, after Drew's feedback). A GitHub job once a month reads
  the official BLS schedules (CPI, jobs, PPI) and the Fed's meeting calendar, compares them with
  `macro_calendar.py`, and sends the admin a notification listing any difference, or a warning when fewer than six
  months of dates remain. One-click accept; dates are never changed silently. The calendar runs to December 2027,
  so the 2028 dates must be added during 2027.
- Tide signals in Lattice (Tide, Sea state, storm warning as conditions in Sets and funnels).
- Expected vs actual for each release (needs a forecast source; consensus data may need a licence).
- After Drew's review: crypto rotation measures he watches; real rates as a candidate current.

## Other

- Funnel studies (how past Candidates did afterwards, on development data only).
- Drew's exact oscillator settings against the published defaults (needs a certification run).
- OKX perpetuals as a futures source (funding and open interest for more coins).
- Multi-language app, as one separate exercise before a public launch (after Strategies and tiers settle): pull all
  on-screen text into per-language files, translate Help and guides as whole documents, a language setting per
  account, notifications and emails in each person's language, a trading-terms glossary, native-speaker review, and
  a check that flags new text without translations. Major languages only; first wave likely English, Spanish,
  Portuguese (Brazil), Chinese (Simplified), Japanese, Korean, German, French; right-to-left (Arabic) later.
- Funnel and Tides training videos: published 12 Nov 2026 (f1-funnels, t1-tides).
- Chart shapes as signals (asked 14 Nov 2026): find the common trading patterns in the candles by code, one
  signal family with a picker (like Sonar markers), each read as "candles ago" so Sets, funnels and notifications
  can use them: head and shoulders (and inverse), double top and bottom, triangles, wedges, flags, channels,
  well-known average crosses (golden and death cross), and candle patterns (engulfing, hammer, doji). Draw each found
  shape on the chart with a hover explanation. Built on the confirmed swing points the structure signals already
  use, so a shape is only reported once it is complete (no peeking ahead), then certified and tested on history
  like every other signal. Start with the few Drew actually uses.

## Done (12 Nov 2026)

- Event markers on the price chart (Fed, CPI, jobs), with a toggle remembered per account.
- Settings → 🤖 AI choices: the AI Navigator per person; news sentiment app-wide by an admin
  (sql/2026-11-25_app_settings.sql); a walkthrough for adding keys as Render and GitHub secrets.

# Angstrom Signals: handover

Written 30 October 2026. It covers the work done and decided in the sessions of 27–30 October 2026, plus the standing background needed to pick the project up cold. It is for the owner (Angus), the admin and co-tester (Drew), and any future Claude or Cursor session.

Read section 1 for what the product is, section 9 for what must be done by hand, and section 10 for what to do next. Everything else is reference.

Nothing secret is stored in this file or in the repository. Where a key or token is needed, only its name is given.

## 1. What the project is

Angstrom Signals is a research dashboard for crypto and equities. Each asset on a person's watchlist gets a score from 0 to 100 built from ten technical factors. The app charts the asset, shows market sentiment from recent headlines, lets people comment and chat, and emails an alert when a score crosses a threshold that person chose.

It is a research tool, not financial advice. The score is presented as a **reading of current conditions, not a forecast** (see section 4).

| Part | Where it lives | Notes |
| --- | --- | --- |
| The app | Streamlit, `app.py` (about 11,500 lines), hosted on Render at app.angstromsignals.com | One big script. Each click reruns it, which is why speed work matters (section 7). |
| Accounts and data | Supabase (Postgres, row-level security) | Schema and policies live in `supabase_rls.sql`. |
| Background worker | `run_alerts.py`, started by the GitHub Action `alerts.yml` | Supabase's own clock (pg_cron) starts it every 5 minutes. GitHub's own schedule is only a backup because it often waits about 2 hours. |
| Emails | Resend, sent by the worker | One shared look in `email_brand.py`. |
| Marketing site and beta form | HostGator, angstromsignals.com, plain HTML plus a few PHP files | The website source is **not in this repository** (see section 9). |
| Tests | `tests/`, run by the `tests.yml` Action | 25 test files. |
| Backtests | `backtest.py` plus the manual `backtest.yml` Action | Results come back as a downloadable report. |

The repository is **public** with an all-rights-reserved `LICENSE` (copyright Angus Marshall). That was a deliberate choice: the owner did not want to close it for now. The consequence is that anyone can read the code but has no right to reuse it. Do not put secrets, personal email addresses or private notes in the repository.

## 2. The people and how to work with them

- **Angus (owner)** is a keen amateur, not a professional coder. Explain steps in plain words and guide him through setup (git, databases, deployment). He prefers **icons with hover explanations** over text labels in the UI, because a multilingual site is planned.
- **Drew (admin)** has the final say on beta requests and reviews the site with Angus. He has "many ideas"; the two plan daily improvement sessions.
- **Cursor** is used for visual polish of the UI. Claude's work is logic, tests, backtests and data code.
- **Screen changes are untested by eye** unless Angus has looked. In these sessions Claude had no way to see the live app (the built-in browser tools were not available in the chat). Every UI change below is therefore marked "needs a look". Angus asked that Claude stop building elaborate test setups to compensate; the practical routine is: Claude uses plain standard Streamlit components, says what is untested, and Angus pastes a screenshot.
- Angus refused installing offline Streamlit wheels ("absolutely not"). Do not suggest it again.

## 3. How the score works (short version)

Full plain-words rules are in the app (the "how the score adds up" popup, built from `score_rules.py`) and in `scoring.py`.

- Start at 50. Ten factors each add or subtract points: RSI, Stochastic, moving averages (SMA), ADX, MACD, Ichimoku, Bollinger Bands, volume, OBV and 7-day performance.
- Each factor's points are multiplied by the user's weight for it (0 turns it off). The result is clamped to 0–100.
- 70 and above reads as strongly positive, 30 and below as strongly negative. These are the default alert lines; users can move them.
- A confluence step rewards agreement between factors.
- **Regime** (`regime.py`): a classifier reads each asset as trending or ranging (ADX 25 or more trending, below 20 ranging) and bullish or bearish (price against the 50 and 200-day averages). A regime changes only after 3 consecutive days so labels do not flicker. When "adaptive weights" is on, trend factors are scaled up in trending regimes and oscillators in ranging ones. **This is optional and off by default.**

## 4. Design decisions and why

| Decision | Why |
| --- | --- |
| The score is a "reading", not a forecast. | Backtests found no predictive edge (section 5). Presenting it as a forecast would be untrue. |
| Adaptive regime weights stay optional and off by default. | They did not beat fixed weights in the backtest. |
| ATR% is shown as "Typical daily move". | It was the only measure that held up in the tests, and it is a volatility measure, not a direction signal. |
| Phase 3 (1-hour and 4-hour data, combined score, timeframe toggle) is paused. | It is the largest and most expensive phase. It only makes sense once the score shows an edge. |
| Nothing becomes a default until a backtest supports it. | Stated rule of the work plan. |
| The repository stays public, with all rights reserved. | Owner's choice. GitHub Pro was costed and declined for now. |
| "Keep me signed in" is opt-in, 30 days, and remembers the last choice per device. | Safer than staying signed in by default. The cookie holds a refresh token, never a password; the remembered choice is a separate cookie holding only the choice. |
| A second main browser tab simply signs the older session out. | Supabase refresh tokens are single-use, so two tabs would fight over them. The owner preferred the simple route. Pop-outs are unaffected. |
| Picking an asset in a pop-out updates the main page, quietly and without scrolling. | Asked for by the owner. |
| Chart choices (indicators, overlay, earnings dates) are saved on the account. | Asked for by the owner. |
| Earnings dates are kept as history, not just the next date. | "It's all useful data for future analysis." Stored in `earnings_history`, kept by a database trigger. |
| Earnings markers show only for stocks, only when the next date is within 6 weeks, with a tick box (on by default). | A date months away would stretch the chart for no benefit. |
| Email alerts are offered two ways: **Instant alerts** and a **Daily digest**, either, both or neither. | Many instant emails on a volatile day were too noisy. |
| The digest: per-person hour and time zone (default 08:00), silent on days with no alerts, first digest goes out at the next chosen hour after switching it on. | Agreed with the owner ("all perfect"). |
| Beta access is approved by Drew through Approve/Reject links in the request email. | Drew has final say. Links are signed so they cannot be guessed. |
| Alert emails already use a branded template. | Confirmed by the owner on 30 Oct. No work needed on look and feel; the remaining item is the sender address (section 8). |

## 5. What the backtests found

Run on BTC-USD, ETH-USD, AAPL and MSFT over 5 years, comparing rank correlation of the score with forward returns against noise floors.

1. Adaptive weights did not beat fixed weights. Every change was inside the noise band, and AAPL got worse at every horizon.
2. No indicator, group or the total score predicted the **direction** of later returns. No row held at any horizon.
3. The score does not predict how **big** the next moves will be. The one signal that held was ATR% at 1, 3 and 7 days.

Still possible and not done: more assets, and an "extremes only" test (does a score above 80 or below 20 behave differently?). Either could still find an edge. To run a backtest, use the **Run Backtest** Action (inputs: tickers, period, and a test of `compare-adaptive`, `score`, `factors` or `volatility`). The backtest cannot be run locally in the cloud workspace because `pandas_ta`, `yfinance` and Streamlit do not install there.

## 6. The agreed work plan

This is the plan agreed on 29 October and updated on 30 October. A longer version with checklists is the Docs artifact "Work plan: market-aware scoring, timeframes and chart indicators". Its goal: make the score adapt to market conditions and timeframe, then show more indicators on the chart, ending each phase with a check, and making nothing the default until a backtest supports it.

| Phase | What | Needs new data? | Main risk | Status |
| --- | --- | --- | --- | --- |
| 1 | Regime classifier on daily bars, behind a switch | No | Labels lag the market | **Built.** Backtested; no edge, so it stays optional and off. A regime **icon per asset** was planned and is **not built**. |
| 2 | Weekly bars and a score per timeframe, with a daily/weekly toggle | No (derived from daily) | Fewer bars on weekly | **Not built.** |
| 3 | 1-hour and 4-hour data, timeframe toggle, combined score and agreement indicator, alert behaviour per timeframe | Yes | Storage, refresh load, stock gaps | **Paused** until the score shows an edge. |
| 4 | Chart indicators with icon toggles | No | Cramped chart, theme colours | **Built and live.** Owner called the chart "very good". |

Phase 3 design notes (for when it restarts): hourly bars are about 24 times the daily volume, so measure database size and free-tier limits first; fetch hourly bars on their own schedule so the 5-minute price refresh stays fast; stock hourly data has overnight and weekend gaps and must say so; 4-hour bars are built from 1-hour bars; the combined score would blend the four timeframes with weekly weighted heaviest and 1-hour for timing.

Three "open decisions" in the plan document are ticked as decided, but **the answers were never written into the document**: whether the combined score is shown to all users or kept as a later pro feature; whether alerts follow one chosen timeframe or are set per timeframe; and whether hourly data's storage and refresh cost is acceptable on the current hosting plan. Confirm them with Angus before Phase 3 restarts.

Who checks what: Claude owns logic, tests, backtests and data code; Angus and Drew judge whether scores and regime labels match their reading of the market and how the screen looks; Cursor does visual polish.

## 7. What has been built (this period)

Everything below is committed and pushed. Latest commit at time of writing: `ce86491` (daily digest). Tests pass in the cloud workspace for the logic; the screen was not seen.

**Scoring and research**
- Regime classifier and optional adaptive weights (`regime.py`, `scoring.py`), backtest comparison (`backtest.py`) and a manual backtest Action.
- ATR% relabelled "Typical daily move (ATR%)" with help text.
- "How the score adds up" popup (`score_rules.py`): plain-words table with the user's own weights. It is a plain table because an earlier sortable version scrambled grouped rows.

**Chart (`chart_plan.py`, `app.py`)**
- Extra indicators: SMA 200, Ichimoku cloud, MACD, Stochastic, ADX, OBV. At most four extra lower panels.
- An overlay option that draws RSI, Stochastic and ADX on the price chart instead of below it. Legend moved under the chart so it no longer collides with the toolbar.
- Earnings markers and the earnings tick box. Past report days are marked from stored history.
- Choices saved per account.

**Earnings data (`data_fetchers.py`, `market_store.py`, `supabase_rls.sql`)**
- A failed lookup no longer overwrites a saved date with "none" (it was turning dates into dashes).
- `earnings_history` table plus a trigger that records every date seen.
- Admin panel shows earnings lookup status. Finnhub key is set (the owner confirmed it in the secrets file).

**Reliability**
- `session_guard.py`: refreshes the Supabase sign-in about two minutes before it expires, so a page left open does not go blank. This was the cause of the blank logos, watching counts, sentiment and earnings: an expired token made the shared reads silently return nothing, and logging out and in fixed it.
- Shared market warnings now say why, at most once per ten minutes per kind, in the Admin area and logs. A fallback to fewer database columns now lasts ten minutes instead of until restart.

**Sign-in and windows**
- "Keep me signed in" (opt-in cookie, restore on refresh, cleared on log-out) and the remembered choice.
- Pop-out windows follow each other through a browser broadcast channel; a pick in a pop-out updates the main page without scrolling.

**Email**
- `email_brand.py`: one branded look (navy header with logo, coloured callout, button, footer) for alert, welcome, invite, barred and digest emails. `email_templates/` holds the matching Supabase sign-up, magic-link and reset emails.
- Beta decision emails: `beta_emails.py`, `beta_worker.py`. When Drew approves or rejects, the worker emails the applicant within about 5 minutes.
- **Daily digest** (`digest.py`, `run_alerts.py`, `alerts.py`, `app.py`): new settings under Configure Alert Rules ("⚡ Instant alerts", "📬 Daily digest", hour, time zone). Details in section 8.

**Housekeeping**
- All-rights-reserved `LICENSE`.
- `tzdata` added to `requirements.txt` so time zones work on Render and in the Action.

## 8. Half-done, unverified and known problems

**Daily digest (just built, never run for real)**
- Needs the SQL re-run (section 9) before the settings appear. Until then the panel shows a short note.
- The settings layout has not been seen on screen. Things to check: the two checkboxes and their hover tooltips; "Send at" and "Time zone" appearing side by side when the digest is ticked; the time zone pre-filled from the browser (relies on a newer Streamlit; falls back to UTC); the "Both are off" line.
- The digest shows crossings since the last digest plus the strongest and weakest current readings. It does **not** show "biggest movers", because yesterday's scores are not stored.
- Instant emails now ignore crossings older than 24 hours, to stop a burst if someone turns instant alerts back on.
- The digest and instant emails use separate markers (`digested_at`, `emailed_at`), so neither hides the other's alerts.

**Beta Approve/Reject links**
- Built end to end and tested against a local database and PHP. The website files are uploaded. A **live test with a real request has not happened yet**.

**Unverified on screen (no live view in these sessions)**
- Chart legend strip height, overlay clutter, earnings label collisions and empty stretches.
- The scoring popup layout.
- "Keep me signed in": that logging out clears it, that unticked refresh logs out, and that a second tab signs the older session out.
- Pop-out pick sync: possible flicker or loops. (Refreshing the main page with pop-outs connected was checked by Angus and worked.)
- Whether the session guard fully prevents the blank-data problem. Angus saw no Supabase warnings and no obvious Render errors when it happened, so if it recurs, check the Admin warnings first.

**Known annoyances and open optimisation**
- Angus feels there are "a whole load of refreshes". Not yet investigated beyond a first look. Candidates: pop-out follow triggers, the extra rerun after a keep-signed-in restore, a 30-second social fragment, and several JavaScript timers (about 0.4, 0.5, 1 and 1.5 second intervals). The Admin "Page timing (last load of the dashboard)" panel and the Render plan are the first things to look at. Unanswered: whether the slowness is on first load after idle (Render sleeping), on every click (Streamlit reruns plus data calls), or only when several tabs or users are active (Render CPU/RAM).
- In overlay mode the RSI guide lines are still drawn (earlier misdescribed as omitted). Right-axis ticks could be rounded (0/25/50/75/100) and the legend tidied. Offered, not requested.
- Per-curve overlay picker: not built.
- The GitHub repository description still reads "Simple level 1 Crypto & Equities trading signals aggregator". The owner must change it by hand (GitHub settings); it cannot be changed from the cloud workspace.
- Website source is not in this repository (see section 9).

## 9. Things only you can do by hand

1. **Re-run `supabase_rls.sql` in full** (Supabase, SQL Editor, paste the whole file, Run). It is safe to repeat. It is required for: the digest columns, `earnings_history`, the beta link functions and tables. Re-run it after every update that touches the database (the last three updates did).
2. **Beta link secret** (once): in the SQL Editor, run the commented snippet near the beta section of `supabase_rls.sql` (update `beta_settings` set `link_secret` ...). Copy the value it returns. Angus reported the website side as set up on 29–30 Oct, so this should already be done; do it again only if you want to invalidate old links.
3. **Website** (HostGator, `public_html`): `send-beta-request.php`, `beta-lib.php`, `beta-decision.php` and a real `beta-config.php` (created from `beta-config.example.php`, holding the Supabase URL, the `sb_publishable_` key and the link secret). Reported done. The PHP source is not in this repository; it lives in the website zip Angus has. Consider committing the website into the repo or a private one.
4. **GitHub Actions secrets** (repo, Settings, Secrets and variables, Actions): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `XAI_API_KEY`, `FRED_API_KEY`, `ALPHAVANTAGE_API_KEY`, `POLYGON_API_KEY`. The Supabase database clock also needs a GitHub token saved in Vault under the name `github_actions_token` (see the comment above the `cron.schedule` block in `supabase_rls.sql`). The token is never committed.
5. **Render:** the app reads its keys from the Streamlit secrets file (Supabase URL and anon key, Finnhub, and others). Check the Render plan and its Metrics tab (CPU and memory) when judging speed.
6. **Resend:** verify angstromsignals.com so `RESEND_FROM` can be an address like alerts@angstromsignals.com. Until then, check the secret: `onboarding@resend.dev` only delivers to the Resend account owner's inbox, so other users would not receive alerts.
7. **Live tests, in this order:**
   - Submit a real beta request, approve it from the email, and check the applicant gets the decision email within about 5 minutes (check spam).
   - Tick Daily digest, set the hour to the next hour, and wait for the worker run. Check the email and that the settings panel looks right.
8. **GitHub repository description:** change it by hand.
9. **Before wider launch:** have a lawyer review the privacy policy, terms, disclaimer and marketing wording. The privacy text was updated for the two sign-in cookies, but it has not had professional review.

## 10. Next steps, in order

1. Live-test Approve/Reject and the daily digest (section 9).
2. Look at the screen for everything listed as unverified in section 8; send screenshots of anything wrong.
3. Cut unnecessary refreshes. Start from the Admin "Page timing" numbers and the Render plan, then audit the rerun sources.
4. Optional chart tidy-ups (remove RSI guide lines in overlay mode, round right-axis ticks, tidy legend).
5. Drew's daily ideas. They may reorder this list.
6. Backlog: custom alert rules; a better "What changed" panel; a worker health message; a regime icon per asset; back-fill of past earnings dates; BTC funding backtests; more assets and an extremes-only backtest to look for a score edge.
7. Phase 2 (weekly bars) only if wanted; Phase 3 only after the score shows an edge and the three open decisions are written down.
8. Update the work-plan document: its backlog still lists "digest alerts", which is now built.

## 11. Working practices and traps

- **Tests:** `pytest` in CI (`requirements-dev.txt`). In the cloud workspace Streamlit, `pandas_ta`, `yfinance`, `plotly` and `supabase` cannot be installed, so `app.py` can only be syntax-checked there, and the source-wiring tests check that code is in place rather than running it.
- **Git:** work on `main`, mirrored to `highlight`. After a commit, push both: `git push origin HEAD:main` and `git push origin HEAD:highlight`. A "1 unpushed commit on highlight" message from the editor hook can be a stale reference; fetch it and compare `git ls-remote origin main highlight`.
- **Local Windows setup:** Python 3.12 (3.11 will not install `pandas-ta`), a virtual environment, `.streamlit/secrets.toml` with the **anon** key only. Never put the service-role key in the app. See `README.md`.
- **Row-level security:** every table is locked to its owner. The worker uses the service-role key, which bypasses it. New tables must have policies written in `supabase_rls.sql`.
- **Shared market data** (`asset_market`) has protective triggers: earnings kept for 6 hours, a logo cannot be overwritten once set. Do not weaken them without reading why.
- **Streamlit habits that bit us:** widgets with keys must be seeded from saved values; `st.table` rather than `st.dataframe` where order matters; helper functions must be defined before first use; fragment reruns (`_rerun_fragment`) versus full reruns (`st.rerun`) change how much of the page redraws.
- **Never use `pkill -f`** with a pattern that matches the shell's own command line.
- **Commit trailers:** commits made through Claude end with a `Co-Authored-By` line and a session link.

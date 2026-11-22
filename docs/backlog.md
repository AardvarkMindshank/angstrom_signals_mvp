# Backlog

Agreed work that is not built yet, so nothing gets forgotten between sessions. Newest first.

## Checks to repair (18 Nov 2026)

- Three browser checks in the v2 CI fail since the "Lattice simplified" families: the Lattice editor check (looks for
  the old "Add Stochastic %K" button), Lattice inside Streamlit, and the training-video / Advisor windows. Not caused by
  Tides (same failures on the run before). Update the scripts to the family → signal → variant lists.

## AI Navigator with tools, and an Elite "research desk" (19 Nov 2026)

Why the Navigator feels weaker than the development assistant: it answers in one go (one question, one reply) from
the help text and the screen, on a mid-size model (claude-sonnet-5-5). It cannot look at real readings, test what it
suggests, or check its own work. The difference is mostly the loop (look, try, check, adjust), not the model.

Plan: give it tools that the app runs, so it works only through the app's own building blocks and rules.
1. Read tools (all tiers, now): list signals, Groups and Sets; an asset's current readings; a Set's answer now and its
   past answers; Tides; Soundings results. Cheap: a few extra calls per question, with the long system prompt cached.
2. Build tools (all tiers, now): draft a Group or Set and open it in the editor (like Soundings' Open as Set). Nothing
   is saved without the user's click.
3. Test tools (Elite, later): run What followed or a Soundings-style study on chosen assets and years as a background
   job, results back in the chat; bigger model and a longer thinking budget; a monthly allowance per user.
4. Optional, later: a hosted sandbox where it can run its own analysis code on the app's data.
Guardrails in the tools themselves: the protected hold-out (from 30 Oct 2024) can't be read, no trading or posting,
each user sees only their own data, a usage budget per user.
Cost estimate (to check against Anthropic's price list before setting limits): a question today is about 21k tokens of
system prompt (cached) plus the answer, a few US cents; with tools, 2 to 4 calls per question, roughly 1.5 to 2 times
today. The Elite desk (bigger model, many steps) could be tens to hundreds of times a Navigator question.

## Soundings: combining the ✅ rise results (on hold, 19 Nov 2026)

- The three ✅ rise results on 100 coins mostly fire on different days (15-28% overlap). A rise followed: none held
  0.86-0.90× usual; any 1: 1.52× (search) / 1.32× (later); any 2: 1.58× / 1.57×; all 3: 2.02× on 141 closes / 1.58×
  on 95 closes (too few to tell 2 from 3 yet). Idea: provided Sets "Rise setups: all 3 agree" and "2 of 3 agree".
  Parked while thinking about how traders would use it to prepare trades. The protected period from Oct 2024 is the
  fair test of the combination (the three were chosen on 2023-24).

## Soundings: next steps (first run 18 Nov 2026)

- **Soundings chart** (Angus's idea, 18 Nov 2026): a coin's price across the top with the timeline under it, and
  below it one row per signal reading or Set, each showing when it fired, lined up with the price; rises and falls
  marked on the price. Built from the saved readings tables (about 5 MB for 25 coins), so it draws instantly.
- Open a pattern as a Set (and so as a scan or funnel stage); ask the AI Navigator about a pattern.
- More coins (survivorship: today's coins only), equities, 4-hour candles, the move definition as a choice.
- Calibrate the lift test's variance factor on synthetic markets (KAPPA 1.2 is borrowed from the research tests).

## "When it turned No" study (asked 18 Nov 2026, for later)

What followed only studies fresh Yes moments against ordinary No days. Add a second study beside it: fresh No moments
(a No after several Yes candles in a row) against days the Set stayed Yes, to show whether the move tends to fade once
a Set switches off (a possible exit cue). Same machinery and honesty rules as What followed (`what_followed.py`):
comparable days, calendar-block resampling, Holm correction, consistency checks, and every window ending before the
protected hold-out (30 Oct 2024). Needs one calibration run (as `what_followed_calibrate.py`) before any verdict is
shown. Shown as a second line under each Set's What followed. Expect many "No clear difference" results.

## Plan agreed 15 Nov 2026: remaining product work and the road to a commercial launch

Suggested order: Strategies step 2 spec and build (Claude) while the owner starts the slow outside steps (legal
entity, Paddle); a data-licence review alongside; then tiers and payments, hardening, and the beta roll-out.

**Product**
1. **Strategies, step 2: tracked plans.** Entry (a Set or sequence), ladder in, exits and ladder out, in typical
   moves and shares of the plan (never money); each watched asset moves Watching → Armed → Building in → Managing →
   Done with alerts at each step; the ladder drawn on the chart. First: a short build spec for review by the owner,
   Drew and the three AIs. Step 1 (sequences in Sets) was built 9 Nov; step 3 (plan studies, same honesty rules as
   What followed) follows. Design: `docs/research/strategies_brief_2026-11-09.md`.
2. **Smaller open items:** "tell me when Armed" alert for sequences; signal families in the Lattice picker; more
   chart shapes (candle patterns, triangles, wedges, flags; head and shoulders, double tops/bottoms and crosses are
   done); Tides readings in Sets and funnels; the monthly macro-calendar check; funnel studies; Drew's oscillator
   settings; OKX perpetuals (all detailed below).
3. **Housekeeping:** email service (proper SMTP for Supabase auth mail, e.g. Resend: the built-in sender allows only
   a few mails an hour); a test login for Claude (the owner's Google account, a normal user, signed in once in the
   desktop app's built-in browser); training videos for the rest of the site (extend the video demo page); translate
   "Max pain" and "0 matches" (left for now).

**Commercial track** (some steps wait on outside parties, so start early)
Decided 17 Nov 2026 (tiers document "Angstrom Signals: membership tiers proposal", Rollout section): build the tiers
and connect Paddle (sandbox only) now, but charge nobody yet: an invite-only free beta, then possibly a free public
launch with the AI Navigator capped per user, then tiers and payments as the user base grows. Show the tiers from the
start with paid features marked "free during the beta". The data-licence review is needed before any public launch,
not only before payments. All four tiers launch together; limits and names live in the database, editable in Admin.
1. **Legal entity:** Paddle, the final NDA, terms and privacy pages all need the company's legal name.
2. **Paddle:** merchant of record (collects sales tax and VAT worldwide). Approval can take days to weeks and needs
   a live website with pricing, terms and a refund policy. The owner signs up; Claude prepares the website pages.
3. **Data licences (important):** Yahoo Finance (via yfinance) does not allow commercial use. Before taking money,
   review every source's licence and plan licensed replacements, with options and costs for the owner's approval.
4. **Membership tiers in the app:** turn the planned free + 2–3 paid tiers into concrete limits, add a plan per
   account with feature checks, then connect Paddle so payments switch tiers automatically.
5. **Beta roll-out:** the invite flow exists (request form, Drew's approval, NDA); still needed: the final NDA,
   the email service, a welcome / onboarding path for testers, and the videos.
6. **Before outsiders arrive:** make the GitHub repo private (check the effect on free GitHub Actions minutes),
   database backups, and error alerts.

## Forex and commodities (proposed by Drew; ChatGPT and Claude views, 15 Nov 2026)

Idea: add currencies (EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD; later EUR/GBP, EUR/JPY) and
commodities (gold, silver, WTI and Brent crude, copper, natural gas; agricultural later) to Angstrom, as an
extension of the existing engine (Signals → Groups → Sets → Prism → Funnels), not as separate systems. ChatGPT
supports it: broader market understanding, cross-market research, wider commercial audience; start with a small
list; decide data sources and licences first; don't let it displace beta readiness or the data-licence review.

Claude's view (agrees, and adds):
1. **Bigger than two more tables.** The app is built for exactly two markets: 109 crypto-or-equity checks across
   44 files (tables, funnels, data, charts, alerts, studies). Full support means turning that into a list of markets,
   each declaring its data source, trading hours, candle sizes and whether volume means anything. Weeks of work,
   worth doing once and properly.
2. **A cheap first step gives most of the research value.** Gold, oil, copper and the dollar index are already
   fetched daily for Tides, and Sets can already read a second, pinned asset (as in "Coinbase leads Bitcoin"). Make
   key commodities and currency pairs usable as conditions in Groups and Sets ("Bitcoin's trend when gold is
   rising") without new tables; fits the backlog item "Tides readings in Sets and funnels".
3. **Licensing applies today.** Tides takes gold and oil from Yahoo futures (GC=F, CL=F, HG=F, DX-Y.NYB), under the
   same no-commercial-use terms as Yahoo equities: the data-licence review must cover them. Free reference rates
   (e.g. European Central Bank daily currency rates) suit context but are daily only; licensed intraday currencies
   and commodities come from paid providers (to be researched and priced for the owner's approval).
4. **Market differences.** Forex trades 24 hours, 5 days a week, with the daily close conventionally at 5pm New
   York (not midnight UTC), which every daily signal and study depends on. Commodity futures roll between contracts,
   creating false jumps unless the series is stitched properly. Missing volume already shows as Unknown, never zero.
5. **Upside:** long, clean daily histories, good for honest studies.

Suggested order: add these sources to the data-licence review now; after Strategies step 2, make key commodities
and currency pairs usable as conditions in Groups, Sets and Tides; decide on full Forex and Commodities tables only
once it is clear whether users want to trade them directly. Open question for the owner and Drew (ChatGPT's): are
these markets to trade, or context for crypto and equities? A practical test: does Drew trade gold, oil or
currencies himself, or watch them to judge crypto and equities?

## Stock indices for equity funnels (Drew's idea, 16 Nov 2026)

Drew: traders tend to focus on one market or index (he named the Dow, Nasdaq, FTSE and DAX), so a single S&P 500
pool for equity funnels could be improved. Today every equity funnel starts from the S&P 500 with a quality gate
(price, dollar volume, about 3 years of history; `equity_universe.py`). Two development approaches:

1. **Quick: choose the US index per funnel** (do soon). Let a funnel's pool be S&P 500, Nasdaq-100 or Dow 30. The Dow
   is almost entirely inside the S&P 500 and the Nasdaq-100 mostly is, so the data source (Yahoo), New York trading
   hours and signals stay as they are; funnels already have a "pool" setting for this. Work: the two extra member
   lists in the equity universe job (plus the few Nasdaq-100 members outside the S&P 500 through the same quality
   gate), and an index picker in the funnel editor.
2. **Bigger: indices outside the US** (FTSE 100, DAX; possibly Nikkei 225 or others later), built together with the
   markets work in "Forex and commodities" (turning the two built-in markets into a list of markets, each with its own
   hours and data source), after the data-licence review. Needs per exchange: its own trading calendar (opening hours,
   holidays, closing time; funnels currently work out closes on New York hours only), price units (London quotes in
   pence), Yahoo ticker endings (.L, .DE …), and licensing: exchange data is often licensed separately, and index
   member lists belong to the index providers (S&P, FTSE Russell, STOXX); Wikipedia lists are fine for development but
   need checking for a paid product.

Open: ask Drew which indices matter most to him.

**Decided 15 Nov 2026:** ready-made (provided) Groups, Sets and funnels keep their English names in every language;
users who copy one can rename it in their own language.

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
- Funnel and Tides training videos: published 12 Nov 2026 (f1-funnels, t1-tides).
- Chart shapes as signals (asked 14 Nov 2026): find the common trading patterns in the candles by code, one
  signal family with a picker (like Sonar markers), each read as "candles ago" so Sets, funnels and notifications
  can use them: head and shoulders (and inverse), double top and bottom, triangles, wedges, flags, channels,
  well-known average crosses (golden and death cross), and candle patterns (engulfing, hammer, doji). Draw each found
  shape on the chart with a hover explanation. Built on the confirmed swing points the structure signals already
  use, so a shape is only reported once it is complete (no peeking ahead), then certified and tested on history
  like every other signal. Start with the few Drew actually uses.
- Signal families in the Lattice picker (agreed 14 Nov 2026): show about 15 families instead of 42 signals
  (Stochastics, Moving averages, Money flow, Divergence, Sonar, Positioning, ...), each with a variant picker and a
  one-line "which one when". Done in the editor only: signal ids, saved Groups and Sets, history replays and the
  certification stay as they are.

## Done (15 Nov 2026)

- Multi-language app: 12 languages live (English, Thai, Spanish, Portuguese (Brazil), German, French, Turkish,
  Vietnamese, Indonesian, Japanese, Korean, Chinese (Simplified)); AI sentiment text in the languages accounts use;
  a test requires every live language to be complete.

## Done (12 Nov 2026)

- Event markers on the price chart (Fed, CPI, jobs), with a toggle remembered per account.
- Settings → 🤖 AI choices: the AI Navigator per person; news sentiment app-wide by an admin
  (sql/2026-11-25_app_settings.sql); a walkthrough for adding keys as Render and GitHub secrets.

## Non-US share trading hours (found 16 Nov 2026)

chart_data.build_candles gives daily share candles New York's hours (09:30-16:00) in the exchange's own time zone
whenever Yahoo's daily metadata has no trading period, as it does for SIE.DE (Xetra really trades 09:00-17:30
Berlin). So a European share's day counts as finished at 16:00 local while it still trades for 90 minutes, and Sets
and funnels can read a part-day candle as closed. Fix: a table of regular hours by exchange time zone (Frankfurt,
London, Paris, Amsterdam, Tokyo, Hong Kong, …), New York's only for US zones. chart_data.py is in the replay
certification hash, so the change needs replay_certify.py re-run and certification.json committed with it.
Also: SIE.DE has no stored logo. Share logos come from Finnhub's company profile (stock_logo_url), whose free tier
mostly covers US listings; a fallback source for European shares would fill these.

## Sonar trend triangles: earlier (for the next session with Drew, raised 20 Nov 2026)

Drew finds the trend-turn triangles (EMA 11 crossing EMA 15, the open-source Cipher A formula) late: on Bitcoin daily
they print a median of 7 candles after the swing low or high (4 to 9). Idea: print them about 2 candles earlier,
e.g. a faster pair (EMA 5 / 11) or a turn of the fast average's slope, as an option beside the current rule. Bring
a side-by-side with his TradingView Cipher A (same coin, timeframe and date) to see whether the paid version uses a
faster rule. Markers already show (faded) on the forming candle since 20 Nov. sonar.markers is certified: a new rule
is a new parameter (default unchanged) or a new version, with a certification run.

## Daily forecast video: colours must follow meaning (20 Nov 2026)

Every up/down colour in the video must say good (green) or bad (red) for that metric, not just the sign of the move:
a rising fear index (VIX) is red. Done for the currents tiles (daily_video.INVERSE_WORDS, forecast.html cls()); check
any new tile against this. Still to do before publishing: the opening and closing sequence with the new brand once
the domain is registered, trimming to 90 seconds, and the daily schedule with an emailed copy to post.

### Navigator clips: hands clip through the wheel (21 Nov 2026)
- In the Navigator's clips (white uniform, mate_b_1) her hands go through the ship's wheel as she turns it. Kept for
  now (decided 21 Nov 2026). When redone: start from a picture with her hands off the wheel (or the wheel out of frame),
  the way King Neptune's trident was taken out, then run her 26 lines again (about $5 on the standard model).

### Daily video: intro and outro after the rebrand (21 Nov 2026)
- After the MarketNavi migration: a short opening and closing sequence with the new name, logo and copyright line
  (brand.py holds the name and logos; brand.SHOW_IN_VIDEO switches the branding on). Then the YouTube upload (wide
  as a video, tall as a Short) and the app playing from YouTube, keeping only the newest copy in our storage.

### Blooper reels (idea, 22 Nov 2026)
- Occasional "blooper" videos where everything goes wrong for the crew (fluffed lines, the wheel spinning, charts
  falling over), each ending with the reveal that the ship's cat caused it all, and the cat winking at the camera.
  For social media, after all the channels are connected. Kept clean and classy, like the rest of the crew.

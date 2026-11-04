# Completing the Signal Library: the original readings, sentiment, and Trend/Stretch/Flow as Groups

Status: draft for review, revision 1 (5 Nov 2026). Nothing here is built yet.

This is step 1 of the agreed sequence:
1. complete the library;
2. design the builder (Groups, Sets and Strategies together, mockup first) and the strategy layer;
3. build the strategy engine (headless, with the signal speed-up);
4. build the drag-and-drop interface.

This step changes nothing users see: the dashboard keeps computing Trend, Stretch and Flow with `signals_v2`
exactly as today.

## 1. Goal

When this step is done:
- every reading behind Trend, Stretch and Flow is also a Signal Library signal;
- market and asset sentiment are signals too;
- three starter Groups (**Trend**, **Stretch**, **Flow**) reproduce the dashboard's readings exactly on the same
  input data.

The builder can then offer the original readings, the newer structure/divergence/flow signals and sentiment from
one panel. Today's three readings become recipes anyone can open, copy and change.

## 2. The ten original readings as signals

Trend, Stretch and Flow are averages of ten components (`signals_v2._components`). Four are partly covered by
existing library signals (trend direction uses the moving averages, momentum direction uses MACD and RSI), but in
a different form (labels, not the continuous component). So each of the ten components becomes its own signal:

| Signal id | Native value (what it reports) | Standard score |
|---|---|---|
| `ma.position` | close vs SMA 50 / 200, in % and in ATRs | v2 "moving averages" |
| `ichimoku.position` | above / inside / below cloud; distance outside it and Tenkan–Kijun gap, in ATRs | v2 "Ichimoku" |
| `macd.level` | MACD line, in ATRs | v2 "MACD line" |
| `macd.acceleration` | MACD histogram, in quarter-ATRs | v2 "MACD histogram" |
| `rsi.level` | RSI (14) | v2 "RSI" |
| `stochastic.level` | Stochastic %K (14, 3) | v2 "Stochastic" |
| `bollinger.position` | position within the bands (0 = lower, 1 = upper) | v2 "Bollinger" |
| `move.seven_day` | 7-day % change, and the same move in expected-move units (ATR% × √7) | v2 "7-day move" |
| `obv.balance` | OBV minus its 20-day average, in average daily volumes × √20 | v2 "OBV" |
| `volume.heavy_candle` | volume ratio, candle body as a share of its range, and heaviness | v2 "heavy-volume candle" |

**Native value first, standard score as one field.**
- Each signal's value is its native reading (an RSI of 63, a Bollinger position of 0.82).
- It also carries one field, `standard_score`: the reading on −1..+1 exactly as the dashboard's Trend, Stretch and
  Flow compute it, with positive meaning up or stretched up. *(Review question A.)*

**One source of truth.** `signals_v2._components` is split into one small function per component, with no change
to what it returns: the existing v2 checks and the overlap checks in CI must stay identical. The new signals call
those same functions. A change to a v2 definition therefore changes both, and is versioned (v2's FINGERPRINT, the
signal's version).

**Timeframes.** The signals accept every timeframe. The standard score keeps v2's scaling, which was designed for
daily bars; on other timeframes it is documented as "the daily definition applied to this timeframe".

Existing signals (`trend.direction`, `momentum.direction`, `volume.relative` and so on) are unchanged.

## 3. Trend, Stretch and Flow as starter Groups

Three new starters, `starter:trend`, `starter:stretch` and `starter:flow`:
- **Members:** the cluster's components on the daily timeframe, as score members with equal weight 1.
- **Transform:** `clip` on the field `standard_score`, from −1 to +1. This is an identity on values already in
  that range.
- **Missing members:** `when_unavailable: exclude`.
- **Minimum coverage:** 1 of n. v2 averages whichever components are present and gives no value when none is.
- **Meaning and question:** copied from `signals_v2.CLUSTERS`.
- **Conditions:** none. The words ("Strong uptrend" …) are presentation, not rules, and stay in the dashboard.

**Exact-equality test.** On the same input frame (synthetic, plus frozen development data for several crypto
assets and shares):
- the Group score equals the v2 cluster value within 1e-9, and the −100..+100 percent is identical;
- the coverage counts match;
- the test runs in CI on every change. *(Review question D.)*

**Live values can differ slightly from the dashboard's.** The dashboard computes from the stored shared daily bars
(`SCORING_BARS` = 500), with its own "last completed bar" rule (shares close at 16:30 New York). The library's
candle loader reads Yahoo through `chart_data`, and shares close at 16:00. So on the live site the two can differ
slightly until they read the same data. This step documents the difference and does not change either source.
*(Review question C.)*

## 4. Sentiment as signals

**Two signals:**
- `sentiment.market`: subjects `market:crypto` and `market:stocks`. The stocks scope is a new market scope.
- `sentiment.asset`: any watchlist asset.

**What they report:**
- **Value:** the latest score on the app's −100..+100 scale.
- **Times:** `observed_at` and `available_at` are both the time the score was recorded.
- **Context:** the recent history, and the change over 7 days.
- **Coverage:** whether the score rested on thin news, where stored.
- **Staleness:** a score older than 36 hours is reported as stale.

**Data.** They read `sentiment_history`, which is append-only with one row per update; `recorded_at` is when the
score was produced and saved. A replay at T uses only rows recorded at or before T.

**Replay.** The history starts on 3 Nov 2026, inside the hold-out period, so these signals are replayable for
display only; research has no sentiment data. They go through the same certification suite as the flow signals,
using synthetic histories that are poisoned after T.

**Limitations, written into the signal:**
- AI-scored headlines;
- not validated as predictive;
- thin-news days can swing the score.

## 5. Certification, lineage and documentation

- **Certification.** Every new signal goes through the replay certification suite (reference, poisoning, cache,
  timestamps, boundaries; candle signals also on frozen development data). Results are committed with the code,
  as now.
- **Lineage.** A new lineage table, version 3, adds the new signals' roots:
  - `price` for most of the ten;
  - `price` and `volume` for OBV and the heavy candle;
  - `sentiment` for the two sentiment signals.

  Stored Groups and Sets pinned to version 2 keep working. New and starter documents use version 3.
- **Documentation.** The signal catalogue (`docs/signal_library_catalogue.md`) is regenerated. Each new signal
  documents its calculation, its native value, its standard score and its limitations.

## 6. Not in scope

- Any change to the dashboard, Trend/Stretch/Flow as shown, alerts, the Signal Matrix or evidence views.
- Unifying the library's and the dashboard's daily data source (question C).
- The builder, strategies, backtests.
- Optimising the swing-point algorithms: that is planned as part of step 3.

## 7. Acceptance

- The ten component signals and the two sentiment signals are registered, documented and certified, or listed as
  not certified with a reason.
- The three starter Groups equal v2 on the same inputs (the CI test in §3).
- `signals_v2` outputs are unchanged: the existing checks, the overlap job and the live golden snapshot pass.
- Lineage v3 is in place; existing stored configs still evaluate.
- The full CI passes.

## 8. Questions for review

- **A. Standard score as a field of each native signal**, computed by the same v2 functions, rather than
  expressing v2's scaling (tanh of ATR-scaled distances, sub-averages) through new Group transform kinds.
  Recommended: the field. It is exact, has a single source of truth, and needs no new transform machinery; users
  can still build their own transforms on the native value.
- **B. One signal per v2 component (ten)** rather than fewer combined signals. Recommended: ten. Each is then
  individually usable, replaceable and weightable in the builder.
- **C. Data source.** Accept and document that library candles (Yahoo via the chart loader) and the dashboard's
  stored daily bars can differ slightly on the live site, and unify them later as a separate task. Recommended:
  accept for now.
- **D. Equality criterion.** Within 1e-9 and an identical −100..+100 percent on identical inputs. Recommended:
  yes.
- **E. Sentiment** as two signals, display-replay only, stale after 36 hours. Recommended: yes.

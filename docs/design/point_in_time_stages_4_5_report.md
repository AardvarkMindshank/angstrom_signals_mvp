# Point-in-time evaluation: Stages 4 and 5 report

Branch `feature/replay-inspector`, built on the merged Stage 3 (main `be3e0a2`). **Not merged and not deployed.**
No user-facing historical functionality has been added.

## Stage 4: admin-only single-date reconstruction

Where: the 🧪 Signal Library panel → **Groups & Sets** tab (admin accounts only, as before).

**How to use it:**
- Tick **"Reconstruct at a past time (one date, UTC)"** and choose a date and time. The default is 30 days ago at
  00:00.
- **Evaluate** then reconstructs the chosen Group or Set (a starter, the example Set, or any saved version you can
  read) for the chosen asset at that moment.
- One date per request; there is no history view.

**Mechanics:**
- A display replay (`replay_display.display_run(max_steps=1)`), reading current providers: the chart's candle
  loader, plus stored flows as of T.
- Only certified signals run; the others show as not replayable.
- Times in the future are refused.

**What it shows:**
- A banner: "As-of reconstruction at … UTC: today's rules on data cut at that time. Descriptive only: it is not
  saved and not used for statistics."
- **Completeness:** complete, limited, partial, or partial and limited. A warning appears whenever the result is
  qualified ("not a complete reconstruction of this time"). The notes cover missing members, critical members,
  unknown vetoes, unknown confirmations and limitations.
- **A table of missing members:** why each is missing, whether it is critical, the effect on score coverage, and
  which confirmations and vetoes became unknown.
- **The usual Group or Set card** (score, conditions, members, diagnostics). For Sets, each Group's completeness is
  shown as well.
- **A "Reconstruction record" expander:**
  - mode, cutoff, the administrative run time, code identity and environment;
  - the hold-out boundary;
  - every input, with its quality and the SHA-256 of the exact cut data;
  - every signal, with its certification.
- **No download.** Reconstructions are not exported; the live result keeps its existing download.

**Tests:**
- `reconstruct()` for one Group: complete, with the display-mode record and input hashes.
- `reconstruct()` for the example Set: partial (the Bitcoin ETF item is live only).
- A future time is refused.
- A Streamlit test shows a stored partial reconstruction: the banner, the completeness label and the qualification
  warning, and no download button.

Live evaluation in the same tab is unchanged.

## Stage 5: certified slicing and reuse of unchanged timeframe calculations

Two shortcuts, both off by default.

**Shortcuts:**
- **Certified slicing** (`shortcut=True`). Indicators are computed once on a timeframe's whole history and sliced
  per cutoff. It is used only for signal/timeframe pairs certified slice-equivalent: 55 pairs, not daily RSI
  divergence and not flows.
- **Reuse of unchanged frames** (`reuse_frames=True`). When a timeframe's cut window holds exactly the same candles
  as at an earlier cutoff (no candle closed in between), the same indicator frame is reused. The inputs are
  identical, so the result is too. There is a bounded cache of 32 frames per run.

**A defect found and fixed.** The first measurement showed no speed-up. Building the replay cache key loaded the
candles, which computed every frame by the exact path before each signal ran, so the shortcuts never took effect.
The key is now the cutoff alone, since within a run the inputs at a cutoff are fixed. The certification suite was
re-run for this code and still certifies 58 of 61 pairs.

**Verified against the exact path (required CI step).** The example Set was replayed at 60 consecutive daily
cutoffs per dataset with each variant, and every step's whole result was compared with the exact path:

| Dataset | Variant | s/step | Peak Python MB | Steps differing from exact |
|---|---|---|---|---|
| Synthetic crypto | A exact | 1.51 | 29 | 0 |
| Synthetic crypto | B reuse frames | 1.45 | 33 | 0 |
| Synthetic crypto | C certified slicing | 1.15 | 30 | 0 |
| Synthetic crypto | D slicing + reuse | 1.14 | 47 | 0 |
| Synthetic share | A exact | 0.71 | 7 | 0 |
| Synthetic share | C certified slicing | 0.46 | 13 | 0 |
| BTC-USD (development) | A exact | 0.30 | 5 | 0 |
| BTC-USD (development) | C certified slicing | 0.18 | 6 | 0 |

Signal-level benchmark (all 1D signals per step, 365 steps): the slice shortcut reduces 0.12–0.13 s/step to
0.08–0.09 s/step on the development data.

**Findings:**
- **Certified slicing** gives a 25–40% speed-up with no difference from the exact path.
- **Frame reuse** adds little for daily stepping. Intraday windows change at every daily cutoff; only weekly frames
  repeat.
- **What remains dominant**, after indicators, is the signal algorithms themselves. Multi-timeframe alignment
  evaluates trend and momentum on all five timeframes, and the swing-point loops used by divergences, structure
  and zones are pure Python.
- A Set replay on crypto still takes about 1.1 s per day, so interactive multi-day histories remain out of scope,
  as agreed.

**Recommendation:**
- Enable certified slicing for display reconstructions; frame reuse is optional.
- Keep the exact path for research and for the certification suite.
- Any further speed-up would come from optimising the swing-point algorithms, which is a separate,
  re-certified change and not proposed now.

## Tests and CI

- New tests: 2 reconstruction tests, 1 Streamlit test, and the Stage 5 CI step that fails if any variant differs
  from the exact path.
- Full local suite: 624 passed.

**Final CI** (commit `ed6911f`): all four jobs pass.
- 670 tests.
- The certification record matches the current code: 58 of 61 pairs certified, unchanged.
- The Stage 5 comparison: every variant equals the exact path at every step.

That run's GitHub machine was faster than the earlier one, and the relative gains held:

| Dataset | Exact | Certified slicing | Slicing + reuse |
|---|---|---|---|
| Synthetic crypto | 0.81 s/step | 0.61 s/step | 0.60 s/step |
| Synthetic share | 0.39 s/step | 0.25 s/step | 0.25 s/step |
| BTC-USD (development) | 0.17 s/step | 0.09 s/step | 0.09 s/step |

Absolute times vary between machines; Render's CPU is slower than GitHub's.

## Ready for review

Waiting for approval before merging Stages 4–5, and before enabling certified slicing for display
reconstructions.

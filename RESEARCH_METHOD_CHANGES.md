# Research method changes

Development-only research code (`research.py`, `research_stats.py`). The live app does not use either file.

## v2 (31 Oct 2026)

1. **Labels stop at the hold-out boundary.** In v1, forward returns were computed on the full price series and only the signal dates were cut. The last development labels therefore used up to 31 bars of hold-out prices (to 12 Dec 2024 for stocks, 29 Nov 2024 for crypto). From v2, every bar on or after 30 Oct 2024 is removed before scoring, so no label, score or histogram can reach past it. A test changes every hold-out price and checks that the development report is identical.
2. **Score histogram and parity check use development dates only.** In v1 they also covered hold-out dates. They used scores only, with no returns.
3. **New primary statistics** (`research_stats.py`). A calibration study on synthetic markets found that the v1 per-asset time-series rank correlation leans towards "Stretch positive" and "Trend negative" even when there is no effect. Tests on it gave false alarms 35–44% of the time at hold-out length. The new statistics are:
   - Claim A: real-time own-history percentile × within-date return rank.
   - Claim B: unchanged spread, now with a studentised test.
   - Claim C: ATR%'s gain in rank correlation over a benchmark.
   
   All use a studentised joint-date block bootstrap with a t reference and a calibrated inflation factor.
4. **Faster cross-section.** The cross-section code was rewritten in numpy. A test checks it gives identical results to the v1 code.
5. **Parity check.** Now run at 90, 200 and 365 bars of history (the app's slider range).

The v1 report is kept unchanged on the reports branch at `research/2026-10-31_0908_limit0/`. To reproduce it, check out commit `a4e7a41` and run with the same price cache.

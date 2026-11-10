# What followed: calibration of the coins / equities parts

10 Nov 2026 · `what_followed_calibrate.py` on the saved prices (86 assets, 17 Sep 2014 to 29 Oct 2024; nothing from the
hold-out), 120 random Sets of each kind, 999 bootstrap runs per test, both measures (gain first, move).

Random Sets know nothing about prices, so every true difference is zero and a sound test passes p ≤ 0.05 about 5% of
the time. "Shared" Sets give every asset the same random Yes days, like a Set pinned to Bitcoin: the hard case for
assets moving together.

| Random Sets | Test | Tests | Passed p ≤ 0.05 |
| --- | --- | --- | --- |
| Independent | All assets | 240 | 0.0% |
| Independent | Coins | 240 | 0.0% |
| Independent | Equities | 240 | 0.0% |
| Independent | Coins vs equities | 120 | 0.0% |
| Shared | All assets | 240 | 2.9% |
| Shared | Coins | 240 | 3.3% |
| Shared | Equities | 240 | 2.1% |
| Shared | Coins vs equities | 120 | 5.8% (within chance of 5%: the 95% upper bound for 120 tests is 8.3%) |

**Result: passed.** The parts keep their false-positive rate at or below 5%, so `SPLIT_VERDICTS` is on: coins and
equities get verdicts, in one Holm family with the pooled tests. The tests are conservative (none passed on
independent random Sets), which is safe but means a small real effect can be missed; that is the existing pooled
method, unchanged here.

**Luck line.** On random Sets the count of unusual assets should match the chance count on average. With the chance
count taken as the average over slides: unusual minus chance was +0.47 assets (shared, 60 Sets, standard error 0.43)
and +0.51 (independent, 60 Sets, 0.29), out of about 86. About half an asset high, inside the noise of a small run; the
card's wording ("typically about N, up to M") covers it. A first run with the median as the chance count read +1.2
for shared Sets, so the average is used.

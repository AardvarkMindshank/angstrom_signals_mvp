# Border-crossing alerts: how often they would fire (13 Nov 2026)

Replay of the proposed alerts (an alert when a reading crosses one of the colour borders, -50 / -20 / +20 / +50) on
the saved daily prices, 30 Oct 2023 to 29 Oct 2024 (the year before the protected hold-out; nothing later is read).
25 crypto assets and 62 equities. Script: research/alerts_replay.py, run by .github/workflows/alerts-replay.yml.

"Confirmed" = a new zone counts only when it holds at the next daily close.

Alerts a week for a 10-asset watchlist (5 crypto, 5 equities), confirmed, both directions together:

| Reading | Leaves neutral | Flips | Gets strongly bullish | Gets strongly bearish | Fades from an extreme | Back to neutral | Today, line 30 | Today, line 50 |
|---|---|---|---|---|---|---|---|---|
| Trend   | 1.6 | 0.0 | 0.8 | 0.5 | 1.3 | 1.6 | 1.5 | 1.2 |
| Stretch | 3.1 | 0.9 | 1.7 | 1.3 | 2.7 | 3.2 | 4.2 | 3.4 |
| Flow    | 2.7 | 0.1 | 0.4 | 0.1 | 0.5 | 2.7 | 3.6 | 1.9 |

Without the hold-at-the-close rule, "leaves neutral" would fire 2.3 (Trend), 5.4 (Stretch) and 7.4 (Flow) times a
week: the rule removes most of the flicker, Flow's above all.

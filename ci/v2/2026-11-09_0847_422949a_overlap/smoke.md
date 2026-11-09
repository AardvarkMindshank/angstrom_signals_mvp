# Signals v2 smoke check (PASS)

Signals 2.0.0, fingerprint 6dd5202c855a, run 2026-11-09 08:43 UTC.
Development rows only (before 2024-10-30). Assets: AAPL, ABBV, ADBE, ADA-USD, ALGO-USD, ATOM-USD.

| Check | Result | Detail |
|---|---|---|
| AAPL: status ok | pass |  |
| AAPL: no 0-100 score key | pass |  |
| AAPL: readings from the starter Groups | pass |  |
| AAPL: trend bounded or missing | pass | 51 |
| AAPL: stretch bounded or missing | pass | 14 |
| AAPL: flow bounded or missing | pass | 26 |
| AAPL: trend coverage full | pass | [3, 3] |
| ABBV: status ok | pass |  |
| ABBV: no 0-100 score key | pass |  |
| ABBV: readings from the starter Groups | pass |  |
| ABBV: trend bounded or missing | pass | -11 |
| ABBV: stretch bounded or missing | pass | -20 |
| ABBV: flow bounded or missing | pass | -26 |
| ABBV: trend coverage full | pass | [3, 3] |
| ADBE: status ok | pass |  |
| ADBE: no 0-100 score key | pass |  |
| ADBE: readings from the starter Groups | pass |  |
| ADBE: trend bounded or missing | pass | -69 |
| ADBE: stretch bounded or missing | pass | -41 |
| ADBE: flow bounded or missing | pass | -26 |
| ADBE: trend coverage full | pass | [3, 3] |
| ADA-USD: status ok | pass |  |
| ADA-USD: no 0-100 score key | pass |  |
| ADA-USD: readings from the starter Groups | pass |  |
| ADA-USD: trend bounded or missing | pass | -14 |
| ADA-USD: stretch bounded or missing | pass | 2 |
| ADA-USD: flow bounded or missing | pass | 16 |
| ADA-USD: trend coverage full | pass | [3, 3] |
| ALGO-USD: status ok | pass |  |
| ALGO-USD: no 0-100 score key | pass |  |
| ALGO-USD: readings from the starter Groups | pass |  |
| ALGO-USD: trend bounded or missing | pass | -30 |
| ALGO-USD: stretch bounded or missing | pass | 1 |
| ALGO-USD: flow bounded or missing | pass | 20 |
| ALGO-USD: trend coverage full | pass | [3, 3] |
| ATOM-USD: status ok | pass |  |
| ATOM-USD: no 0-100 score key | pass |  |
| ATOM-USD: readings from the starter Groups | pass |  |
| ATOM-USD: trend bounded or missing | pass | -9 |
| ATOM-USD: stretch bounded or missing | pass | -16 |
| ATOM-USD: flow bounded or missing | pass | 22 |
| ATOM-USD: trend coverage full | pass | [3, 3] |
| matrix: five v2 rows | pass |  |
| matrix: earlier days unchanged by later bars | pass |  |
| evidence: built | pass |  |
| evidence: version 2, Trend reading | pass |  |
| evidence: fingerprint | pass |  |
| evidence: text names the Trend reading | pass |  |
| alerts: Trend up and down opened | pass | {'TREND_DOWN', 'TREND_UP'} |
| alerts: messages say not a forecast | pass |  |
| digest: shows Trend | pass |  |

| Timing | Seconds |
|---|---|
| watchlist rows (each) | 0.10 |
| signal matrix | 0.68 |
| evidence record (one stock) | 4.17 |

Peak memory of the whole run: 317 MB.

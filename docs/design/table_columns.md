# Reading columns in the asset tables

Each watchlist table shows the readings the account chooses (⚙️ Columns): Signal Groups (score or label) and
Signal Sets (✓ Yes, ✕ No, ? Unknown), in two sections that fold sideways. The default is Trend, Stretch and Flow.
Hover explains a cell; clicking it opens the Group or Set in Angstrom Lattice.

## Where the answers come from

| Column reads | Worked out by | How fresh | Stored |
|---|---|---|---|
| Daily candles only | The dashboard, from the stored daily bars | As of the last daily close | Nothing extra |
| 4-hour, hourly (or weekly with intraday) | The background worker (`column_answers.py`) at each close of its shortest timeframe (at least hourly) | "as of HH:MM UTC"; ⏳ once a newer close has passed without an answer | One small row per definition and asset |

We decided against storing intraday candles: about 24 times the rows for hourly data, and every dashboard visit
would download them (database egress, which is the limit we hit). The worker instead reads candles from the price
provider through the same point-in-time reconstruction Prism uses and keeps only the latest answer.

- Only chosen columns are worked out. A definition is keyed by a hash of its content, so accounts that chose the same
  Group or Set share one answer.
- Crypto runs at every close. Shares are held at the last New York close outside trading hours, so a closed market is
  worked out once.
- The worker spends at most two minutes per pass; anything left waits for the next pass.
- A column with no answer yet shows "—", with a hover saying the first answer arrives within the hour.

Table: `column_answers` (`sql/2026-11-11_column_answers.sql`), readable by signed-in accounts, written by the worker.

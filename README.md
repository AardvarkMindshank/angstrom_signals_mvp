# Angstrom Signals

A research dashboard for crypto and equities. It signs each person in with Supabase, scores a watchlist with ten technical factors, and can email an alert when a score crosses that person's thresholds.

This is a research prototype, not financial advice.

## What it does

- Scores RSI, Stochastic, moving averages, ADX, MACD, Ichimoku, Bollinger Bands, volume, OBV, and 7-day performance
- Saves watchlists, weights, and alert rules on the signed-in account
- Charts price, moving averages, Bollinger Bands, volume, and RSI
- Re-arms an alert after the score leaves the threshold, so the same asset can alert again later

A score of 50 is neutral. 70 and above is a strong bullish setup. 30 and below is a strong bearish setup.

## Windows setup

1. Install Python 3.12 from https://www.python.org/downloads/ and check **Add python.exe to PATH**. `pandas-ta` does not install on 3.11.
2. In this folder:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Create `.streamlit/secrets.toml` with the **anon** key from Supabase (Project Settings → API). Do not put the service-role key here.

```toml
[supabase]
url = "https://YOUR_PROJECT.supabase.co"
anon_key = "YOUR_ANON_KEY"
```

4. In the Supabase SQL editor, run `supabase_rls.sql`. That turns on row-level security so each account can only read and write its own rows. The alert worker uses the service-role key, which bypasses those policies.
5. Start the dashboard:

```
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Alerts

The dashboard records an in-app alert when a score crosses a boundary. `run_alerts.py` emails that crossing once, including when the dashboard recorded it first. It does not email again while the score stays past the boundary.

For a local run, set:

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
RESEND_API_KEY
RESEND_FROM
```

`RESEND_FROM` must be a sender on a domain you have verified in Resend. The default `onboarding@resend.dev` address only delivers to the mailbox that owns the Resend account.

GitHub Actions runs the worker from `.github/workflows/alerts.yml` about every 5 minutes, including when the dashboard is closed. Add these repository secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, and `RESEND_FROM`. Scheduled runs can start late, and GitHub pauses them on private repos that stay inactive.

## Market sentiment

Under the chart, the selected asset gets a 0–100 sentiment score from headlines in the last 7 days. The newest headline is listed first, and the number at the top is the average of the article scores. Under the short summary, Positive and Negative each add a paragraph drawn from those same headlines. Green, amber, and red match the technical score colors. The two scores stay separate, and sentiment does not change the technical score or fire alerts.

After an asset has been opened, that score also appears in the Sentiment column of the tables. A dash means it has not been scored yet. Clicking the colored score highlights the asset and jumps to its headlines. The score is stored once per asset and shown to every account for 12 hours. Click a column title to sort that table. It starts with the strongest score at the top.

The 30-day trend column is a small line of the same move shown in **30d %**. Both are green when that move rises by about 2% or more, red when it falls by about 2% or more, and orange when it stays inside about 2%. Those closes are stored on the same shared row, including by the alert worker. Run `supabase_rls.sql` again so the `asset_market` table exists.

The Watching column counts how many accounts have that asset on a watchlist. It shows the count only, not who those accounts are. Run `supabase_rls.sql` again so the `asset_holder_counts` function exists.

Each person can agree or disagree with the current headline sentiment. The buttons sit in an outlined box. Disagreeing opens a score under those buttons: 0, 20, 40, 60, 80, 100, or any number they type from 0 to 100. A picked score also fills the type box, and a typed number saves on its own. The thumbs and a colored box with the average of the personal scores appear at the bottom of Your take, and again under the Crowd heading in each table. That box matches the Sentiment column and updates when a score is clicked or typed. Hovering the down thumb shows the spread around that average. Under the thumbs, each account can post one comment of up to 160 characters. A row of faces under the box adds an emoticon. Posting again replaces that person's comment. A speech balloon appears beside the thumbs, and in the Comments column, when any comment exists. Clicking it slides in the social signals stream from the right. Comments are newest first, with the person's picture, name, time, and the sentiment they were answering. The stream can be narrowed to positive, negative, or mixed coverage. All assets shows every comment. My watchlists shows only the assets in the crypto and equity tables. One asset or one person can be chosen too. Refreshing the sentiment drops the old thumbs and personal scores, because they applied to the previous score. A comment stays for 12 hours from when it was posted, and keeps the sentiment it was answering, even after a newer score arrives. Run `supabase_rls.sql` again so `sentiment_votes`, `sentiment_crowd`, and `sentiment_comments` exist.

## Feedback

The sidebar form takes an issue or an enhancement. Each note is stored in `feedback_notes` with the account, the email, the time, and status `submitted`.

The same note is emailed through Resend when this block is in the Streamlit secrets. Use the Resend key and sender already used for alerts, and the inbox that should receive the notes:

```toml
[resend]
api_key = "..."
from_email = "Angstrom Signals <alerts@angstromsignals.com>"
feedback_to = "you@example.com"
```

Do not commit that file. Until `feedback_to` and `api_key` are set, the note is still saved.

Headlines come from Google News. Grok scores them. Add a key from the [xAI console](https://console.x.ai/) to `.streamlit/secrets.toml`:

```toml
[ai]
xai_api_key = "YOUR_XAI_API_KEY"
```

Put the same block in the Streamlit Cloud app secrets. The result is cached for 12 hours per asset. Without the key, the headlines still show and the score waits.

Asset logos sit to the left of each name. Crypto logos come from CoinGecko. Stock logos come from Finnhub's company profile. Add a free key from [Finnhub](https://finnhub.io) to the same secrets file:

```toml
[finnhub]
api_key = "YOUR_FINNHUB_API_KEY"
```

The logo address is stored once per asset. Run `supabase_rls.sql` again so `asset_market` has a `logo_url` column. A letter shows when a logo is missing.

## Data notes

Crypto ids are CoinGecko ids (`bitcoin`, `polkadot`, `dogecoin`). The app maps those to Yahoo tickers. If Yahoo has no history, it falls back to CoinGecko candles, which do not include volume, so the volume and OBV factors stay neutral for that asset.

The history slider applies to both crypto and stocks. Refresh reloads prices for the current session only.

## Hosting

The dashboard is a long-running Python process. A typical Hostgator shared plan serves PHP and will not run this app. The usual setup is to keep the domain's DNS at Hostgator and point the name at a host that can run Python. That step comes after the app itself is stable.

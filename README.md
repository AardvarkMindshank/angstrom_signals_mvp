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

GitHub Actions runs the worker from `.github/workflows/alerts.yml` about every 5 minutes, including when the dashboard is closed. That run saves shared prices, and it replaces market sentiment that is older than 12 hours. Add these repository secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, and `XAI_API_KEY` (the same xAI key the app uses for sentiment). Scheduled runs can start late, and GitHub pauses them on private repos that stay inactive.

## Market sentiment

Under the chart, the selected asset gets a 0–100 sentiment score from headlines in the last 7 days. The newest headline is listed first. Each row has the link, the date, a one-sentence AI Summary, and that article's score. A dash in AI Summary means the score was saved earlier, so Refresh fills it in. The number at the top is the average of the article scores. Under the short summary, Positive and Negative each add a paragraph drawn from those same headlines. Green, amber, and red match the technical score colors. The two scores stay separate, and sentiment does not change the technical score or fire alerts.

After an asset has been opened, that score also appears in the Sentiment column of the tables. A dash means it has not been scored yet. Clicking the colored score highlights the asset and jumps to its headlines. The score is stored once per asset and shown to every account for 12 hours. Click a column title to sort that table. It starts with the strongest score at the top.

The 30-day trend column is a small line of the same move shown in **30d %**. Both are green when that move rises by about 2% or more, red when it falls by about 2% or more, and orange when it stays inside about 2%. Those closes are stored on the same shared row, including by the alert worker. Run `supabase_rls.sql` again so the `asset_market` table exists.

The Watching column counts how many accounts have that asset on a watchlist. It shows the count only, not who those accounts are. Run `supabase_rls.sql` again so the `asset_holder_counts` function exists.

Each person can agree or disagree with the current headline sentiment. The buttons sit in an outlined box. Disagreeing opens a score under those buttons: 0, 20, 40, 60, 80, 100, or any number they type from 0 to 100. A picked score also fills the type box, and a typed number saves on its own. The thumbs and a colored box with the average of the personal scores appear at the bottom of Your take, and again under the Crowd heading in each table. That box matches the Sentiment column and updates when a score is clicked or typed. Hovering the down thumb shows the spread around that average. Under the thumbs, each account can post one comment of up to 160 characters. A row of faces under the box can be added to the comment. Posting again replaces that person's comment. A speech balloon appears beside the thumbs, and in the Comments column, when any comment exists. Clicking it, or the arrow on the right edge of the page, opens Social signals and chat. Refreshing the sentiment drops the old thumbs and personal scores, because they applied to the previous score. A comment stays for 12 hours from when it was posted, and keeps the sentiment it was answering, even after a newer score arrives. Thumbs, personal scores, and comments are stored in `sentiment_votes` and `sentiment_comments`.

## Social signals and chat

The arrow on the right edge, or a speech balloon, opens a panel. The top half is the social signals stream. The bottom half is a general chat. The gray bar between them can be dragged. Close, the shaded area, or Escape closes the panel. Pin, beside Close, keeps the panel open and leaves the rest of the page free to use. The shaded area and Escape no longer close it while it is pinned.

Signal comments are newest first. Each one shows the person's picture, name, time, and the sentiment they were answering. A note stays for 12 hours, and a reply stays with it for the same 12 hours. All, Positive, Negative, and Mixed narrow the list by that coverage. Under Asset, All assets is every comment. My watchlists is that account's crypto and equity tables. My Crypto Watchlist and My Equities Watchlist each show one list. Crypto market and Stock market sit above the individual assets. All assets or a watchlist is saved on the account. One asset can be chosen too.

Under Person, All people shows everyone. Favourites shows notes from people that account has starred, including a reply they wrote. A star beside another person's name adds them, and the filled star removes them. That list is saved on the account. One person can be chosen too. A note stays in the list when that person wrote it or replied under it.

The green thumb and the red thumb each show a count. Any note can be marked, including one the same person posted. The same thumb again clears the mark. The curved arrow replies. The trash can deletes a note that person posted, and deleting a comment also removes the replies under it.

The chat is a shared room and is not tied to an asset. Notes are newest first and they stay. The panel shows the newest 60 conversations and the replies under them. Older notes stay stored. The Person list matches the stream, including Favourites. Enter posts the box at the bottom. Shift and Enter starts a new line. The same row of faces sits under the box. A reply to a reply is added under the original comment. Thumbs and delete work the same way as on the stream.

One search box at the top filters the stream and the chat together. It matches a note, a reply, a person's name, or, on the stream, the asset. It searches the notes already on the panel, so it does not look through chat older than those 60 conversations.

Run `supabase_rls.sql` again so the chat, replies, votes, deletes, and the person id behind each star are installed.

## Market sentiment

Above Quick Snapshot, the crypto market is one section and the stock market is the next. Each uses the same layout as an asset's sentiment: score on the left, Your take on the right, then the articles. Your take matches an asset: agree, disagree, a score from 0 to 100, and one short comment. Thumbs and personal scores are stored in `market_mood_votes` and clear when that market is refreshed. Comments use the same 12-hour comment store, labeled Crypto market or Stock market. Both use the same headline score as an asset, including the positive and negative paragraphs and a one-sentence AI Summary on each article, after the date. They are stored in `market_mood`, shared by every account for 12 hours, and they do not change a technical score or send an alert. Run `supabase_rls.sql` again so those tables exist. The search wording can be tightened later.

## Feedback

The sidebar form takes an issue or an enhancement. Each note is stored in `feedback_notes` with the account, the email, the time, and status `submitted`.

The same note is emailed through Resend when this block is in the Streamlit secrets. Use the Resend key and sender already used for alerts, and the inbox that should receive the notes:

```toml
[resend]
api_key = "..."
from_email = "Angstrom Signals <alerts@angstromsignals.com>"
feedback_to = "you@example.com"
```

Do not commit that file. GitHub secrets are not visible to this app. The same names can also sit at the top of the Streamlit secrets as `RESEND_API_KEY`, `RESEND_FROM`, and `FEEDBACK_TO`. The note is still saved when the email is not sent, and the form says why.

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

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

Under the chart, the selected asset gets a 0–100 sentiment score from headlines in the last 7 days. Green, amber, and red match the technical score colors. The two scores stay separate.

Headlines come from Google News. Grok scores them. Add a key from the [xAI console](https://console.x.ai/) to `.streamlit/secrets.toml`:

```toml
[ai]
xai_api_key = "YOUR_XAI_API_KEY"
```

Put the same block in the Streamlit Cloud app secrets. The result is cached for one hour per asset. Without the key, the headlines still show and the score waits.

## Data notes

Crypto ids are CoinGecko ids (`bitcoin`, `polkadot`, `dogecoin`). The app maps those to Yahoo tickers. If Yahoo has no history, it falls back to CoinGecko candles, which do not include volume, so the volume and OBV factors stay neutral for that asset.

The history slider applies to both crypto and stocks. Refresh reloads prices for the current session only.

## Hosting

The dashboard is a long-running Python process. A typical Hostgator shared plan serves PHP and will not run this app. The usual setup is to keep the domain's DNS at Hostgator and point the name at a host that can run Python. That step comes after the app itself is stable.

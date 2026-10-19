# Crypto & Equity Signals MVP – Phase 1

A simple, beginner-friendly research dashboard that fetches crypto and stock data, computes basic scores, and displays interactive charts.

## What it does
- Pulls live/recent prices for a small watchlist of cryptos (CoinGecko) and stocks (yfinance).
- Calculates simple technical indicators (RSI, moving averages, etc.).
- Generates a basic composite score (0–100).
- Shows an interactive Streamlit dashboard with charts and a score table.
- Easy to edit and extend.

## Windows Setup Guide (Step by Step)

### 1. Install Python
1. Go to https://www.python.org/downloads/
2. Download the latest Python 3.11 or 3.12 installer (Windows).
3. Run the installer.
4. **Important**: Check the box that says **"Add python.exe to PATH"** at the bottom.
5. Click Install Now.
6. After installation, open a new **Command Prompt** (search for "cmd" in the Start menu) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.x`. If not, restart your computer and try again.

### 2. Download and Extract the Project
1. Download the files from this chat (or the zip if provided).
2. Create a folder, for example: `C:\Users\YourName\crypto_signals_mvp`
3. Put all the `.py` files and `requirements.txt` into that folder.

### 3. Create a Virtual Environment (recommended)
Open Command Prompt and navigate to the project folder:
```
cd C:\Users\YourName\crypto_signals_mvp
```
Then run:
```
python -m venv venv
```
Activate it:
```
venv\Scripts\activate
```
You should now see `(venv)` at the start of your command prompt.

### 4. Install the Required Packages
With the virtual environment activated, run:
```
pip install -r requirements.txt
```
This may take a minute or two. Wait until it finishes.

### 5. Run the Dashboard
Still in the same Command Prompt (with `(venv)` active), run:
```
streamlit run app.py
```
Your browser should automatically open to a local address (usually `http://localhost:8501`).

### 6. If Something Goes Wrong
- Copy the full error message and paste it here — I’ll help you fix it.
- Common issues:
  - Python not found → reinstall and check the PATH box.
  - `streamlit` not found → make sure the virtual environment is activated (`venv\Scripts\activate`).
  - Internet connection needed for the first data fetch.

### Stopping the App
In the Command Prompt window, press `Ctrl + C` to stop Streamlit.

## Next Steps After It Runs
- Edit the watchlist inside `app.py` (look for the `WATCHLIST` section).
- Add more coins or stocks.
- Tell me what you want to improve (more indicators, better scoring, alerts, etc.).

Enjoy exploring!

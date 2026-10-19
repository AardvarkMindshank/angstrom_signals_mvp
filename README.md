# Crypto & Equity Signals Dashboard

A research-focused Streamlit dashboard that fetches crypto and equity data, computes a multi-factor technical score, and displays interactive charts with volume and RSI.

## Features
- Multi-factor scoring (RSI, Stochastic, SMAs, MACD, Bollinger Bands, volume confirmation)
- Graphical progress bars for scores in the tables
- 7-day change, ATR volatility, and volume ratio metrics
- Interactive chart with price, moving averages, Bollinger Bands, volume, and RSI
- Clean layout with snapshot metrics at the top

## Windows Setup Guide

### 1. Install Python
1. Go to https://www.python.org/downloads/
2. Download the latest Python 3.11 or 3.12 installer.
3. Run the installer and **check “Add python.exe to PATH”**.
4. Open a new Command Prompt and verify: `python --version`

### 2. Extract the Project
Unzip the files into a folder, e.g. `C:\Users\YourName\crypto_signals_mvp`

### 3. Create and Activate a Virtual Environment
```
cd C:\Users\YourName\crypto_signals_mvp
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies
```
pip install -r requirements.txt
```

### 5. Run the Dashboard
```
streamlit run app.py
```
Your browser should open to `http://localhost:8501`.

### Tips
- Edit the `CRYPTO_WATCHLIST` and `STOCK_WATCHLIST` dictionaries near the top of `app.py` to change assets.
- Data is cached for 5 minutes. Refresh the page to pull fresh data.
- This is a research prototype — not financial advice.

### Stopping the App
Press `Ctrl + C` in the Command Prompt.

# TradingView chart browser check

24/24 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (182.5 of 182.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  03 Nov '26 04:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 2.6K | RSI (14) 36.39 | MACD Hist -0.6939 · MACD -2.87 · Signal -2.18 | Stochastic (14, 3) 59.80 | ADX (14) 20.68 | On-balance volume OBV -59.2K · OBV average -47.6K)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  21 Oct '26 00:00)
- PASS mouse wheel zooms in (182.5 -> 165.8 candles)
- PASS drag pans back in time (428.6 -> 394.5)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (394.5..560.3 vs 394.0..560.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (394.0)
- PASS reset button returns to the chosen range (182.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: room on the right for the next earnings date (519.0)
- PASS equity daily: earnings lines sent (2)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  02 Nov '26 14:30 last closed)
- PASS equity 1h: note names New York time
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (182.5 -> 22.3 candles)
- PASS touch: sideways drag pans (emulated) (508.7 -> 497.9)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 325)
- PASS no browser errors (touch)

# TradingView chart browser check

25/25 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (188.5 of 188.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  07 Nov '26 04:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 0 | RSI (14) 40.64 | MACD Hist -180.38 · MACD -660.30 · Signal -479.92 | Stochastic (14, 3) 17.30 | ADX (14) 30.94 | On-balance volume OBV -1.58B · OBV average -442.38M)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  25 Oct '26 04:00)
- PASS mouse wheel zooms in (188.5 -> 171.3 candles)
- PASS drag pans back in time (269.2 -> 231.6)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (231.6..404.1 vs 232.0..404.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (232.0)
- PASS reset button returns to the chosen range (188.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: earnings lines sent (1)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  06 Nov '26 15:30 last closed)
- PASS equity 1h: note names New York time
- PASS largest chart (15m, 1 month, every indicator) draws in under 1.5 s (3236 candles, 1237 KB, 200 ms including fetch)
- PASS zooming the largest chart stays responsive (382 ms for 10 wheel steps)
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (188.5 -> 23.3 candles)
- PASS touch: sideways drag pans (emulated) (355.1 -> 343.3)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 329)
- PASS no browser errors (touch)

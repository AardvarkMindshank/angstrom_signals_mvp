# TradingView chart browser check

25/25 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (188.5 of 188.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  03 Nov '26 08:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 3.55B | RSI (14) 39.90 | MACD Hist -15.33 · MACD -496.93 · Signal -481.60 | Stochastic (14, 3) 20.82 | ADX (14) 25.04 | On-balance volume OBV 9.56B · OBV average 11.71B)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  21 Oct '26 04:00)
- PASS mouse wheel zooms in (188.5 -> 171.3 candles)
- PASS drag pans back in time (269.1 -> 233.0)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (233.0..404.3 vs 233.0..404.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (233.0)
- PASS reset button returns to the chosen range (188.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: earnings lines sent (1)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  02 Nov '26 15:30 last closed)
- PASS equity 1h: note names New York time
- PASS largest chart (15m, 1 month, every indicator) draws in under 1.5 s (3236 candles, 1233 KB, 270 ms including fetch)
- PASS zooming the largest chart stays responsive (520 ms for 10 wheel steps)
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (188.5 -> 23.1 candles)
- PASS touch: sideways drag pans (emulated) (354.8 -> 343.2)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 340)
- PASS no browser errors (touch)

# TradingView chart browser check

25/25 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (188.5 of 188.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  03 Nov '26 12:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 3.12B | RSI (14) 47.63 | MACD Hist 37.27 · MACD -434.14 · Signal -471.41 | Stochastic (14, 3) 33.43 | ADX (14) 24.14 | On-balance volume OBV 10.05B · OBV average 12.14B)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  21 Oct '26 08:00)
- PASS mouse wheel zooms in (188.5 -> 171.3 candles)
- PASS drag pans back in time (269.1 -> 233.0)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (233.0..404.3 vs 233.0..404.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (233.0)
- PASS reset button returns to the chosen range (188.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: earnings lines sent (1)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  03 Nov '26 11:30 last closed)
- PASS equity 1h: note names New York time
- PASS largest chart (15m, 1 month, every indicator) draws in under 1.5 s (3236 candles, 1235 KB, 208 ms including fetch)
- PASS zooming the largest chart stays responsive (347 ms for 10 wheel steps)
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (188.5 -> 23.1 candles)
- PASS touch: sideways drag pans (emulated) (354.8 -> 343.2)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 337)
- PASS no browser errors (touch)

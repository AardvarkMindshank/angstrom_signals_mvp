# TradingView chart browser check

25/25 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (188.5 of 188.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  09 Nov '26 08:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 10.49B | RSI (14) 32.67 | MACD Hist -113.91 · MACD -719.33 · Signal -605.43 | Stochastic (14, 3) 28.12 | ADX (14) 40.09 | On-balance volume OBV 2.02B · OBV average -999.04M)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  27 Oct '26 08:00)
- PASS mouse wheel zooms in (188.5 -> 171.3 candles)
- PASS drag pans back in time (269.2 -> 232.8)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (232.8..404.1 vs 233.0..404.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (233.0)
- PASS reset button returns to the chosen range (188.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: earnings lines sent (1)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  06 Nov '26 15:30 last closed)
- PASS equity 1h: note names New York time
- PASS largest chart (15m, 1 month, every indicator) draws in under 1.5 s (3236 candles, 1235 KB, 249 ms including fetch)
- PASS zooming the largest chart stays responsive (507 ms for 10 wheel steps)
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (188.5 -> 23.3 candles)
- PASS touch: sideways drag pans (emulated) (355.4 -> 343.6)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 344)
- PASS no browser errors (touch)

# TradingView chart browser check

25/25 passed.
Touch checks use Chromium's iPad emulation with real touch events; they are not a test on a physical iPad.

- PASS draws price pane plus volume, RSI, MACD, Stochastic, ADX, OBV panes (7)
- PASS opens on the chosen range (188.5 of 188.5 candles)
- PASS legend shows last closed candle with OHLCV (Bitcoin · 4 hours  10 Nov '26 04:00 last closed)
- PASS note explains the forming candle (when there is one) (true)
- PASS pane titles are placed (Volume 112.79M | RSI (14) 42.62 | MACD Hist 28.40 · MACD -571.87 · Signal -600.27 | Stochastic (14, 3) 52.65 | ADX (14) 41.72 | On-balance volume OBV -176.21M · OBV average -303.95M)
- PASS TradingView attribution logo present
- PASS crosshair hover updates the OHLCV legend (Bitcoin · 4 hours  27 Oct '26 20:00)
- PASS mouse wheel zooms in (188.5 -> 171.3 candles)
- PASS drag pans back in time (269.1 -> 234.3)
- PASS rerun with unchanged data keeps the same chart and view
- PASS changing indicators keeps the visible position (234.3..404.4 vs 234.0..404.0)
- PASS overlay mode draws oscillators on the price pane (fewer panes) (2)
- PASS view survives the chart being rebuilt from scratch (234.0)
- PASS reset button returns to the chosen range (188.5)
- PASS equity daily: price, volume and RSI panes (3)
- PASS equity daily: earnings lines sent (1)
- PASS equity 1h: legend time is New York clock (Apple (AAPL) · 1 hour  09 Nov '26 15:30 last closed)
- PASS equity 1h: note names New York time
- PASS largest chart (15m, 1 month, every indicator) draws in under 1.5 s (3236 candles, 1032 KB, 237 ms including fetch)
- PASS zooming the largest chart stays responsive (519 ms for 10 wheel steps)
- PASS no browser errors (desktop)
- PASS touch: pinch zooms in (emulated) (188.5 -> 23.1 candles)
- PASS touch: sideways drag pans (emulated) (353.9 -> 342.4)
- PASS touch: vertical swipe scrolls the page (emulated) (0 -> 338)
- PASS no browser errors (touch)

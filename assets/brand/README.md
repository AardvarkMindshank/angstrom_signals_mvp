# MarketNavi.ai production assets

Tagline: AI-POWERED MARKET NAVIGATION

These are clean vector redraws of the approved generated concept. Geometry and typography have been rebuilt; they are not a pixel-perfect trace. All SVG lettering is outlined into paths. No embedded bitmap, external font, texture or background is used in the full, horizontal, mark and standalone sail logos.

## Font

Segoe UI Bold (wordmark and tagline). This is the matching font chosen for the redraw, not a verified identification of the font in the generated concept. Font files are not included; outlined logos require no font installation.

## Exact production colours

| Use | HEX |
| --- | --- |
| Navy | #061A32 |
| Gold on dark | #E8BD54 |
| Gold on light | #A8750B |
| Teal on dark | #00CDBB |
| Deep teal on light | #007F73 |
| Red candles | #E34B55 |
| Ivory lettering on dark | #F8F7F2 |
| White | #FFFFFF |

All artwork uses flat fills. These are the exact codes in this deliverable; generated preview pixels did not establish a unique original palette.

## File guide

- full-dark / full-light: full compass, sail, waves, candle emblem, name and tagline. Transparent SVG and 1200 x 900 PNG.
- horizontal-dark / horizontal-light: sail and waves to left of name; no tagline. Transparent SVG, PNG at 40px high and @2x PNG at 80px high. Set CSS height:40px; width:auto. SVG canvas includes a small safety margin.
- mark-dark / mark-light: full emblem with no text; transparent SVG and PNG.
- sail-waves-dark / sail-waves-light: simple mark with no text, transparent SVG and 512px PNG.
- app-icon-dark / app-icon-light: 1024px SVG and PNG, rounded navy or white square; corners outside the shape are transparent.
- favicon-dark / favicon-light: dedicated simplified 32-unit vector; transparent PNGs at 16, 32 and 48px. The unsuffixed PNG is 32px.
- favicon.svg / favicon.ico / favicon-16.png / favicon-32.png / favicon-48.png: default navy-backed favicon, suitable for both browser themes. ICO contains 16, 32 and 48px entries.
- apple-touch-icon.png: 180px; app-icon-192.png and app-icon-512.png: navy app icons for web use.
- asset-preview.png: overview of the actual exports, with favicons also shown at native 16px and 32px.

Dark means artwork intended for a dark surface; light means artwork intended for a light surface. The full and horizontal logos have transparent backgrounds. Only the app tiles and default favicon include a filled background.

## Website installation

Copy the selected assets into your public folder. Add:

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
```

Use horizontal-light.svg for a light header and horizontal-dark.svg for a dark header. Set its height to 40px. Keep the tagline on larger placements; use the horizontal lockup for the navigation bar.

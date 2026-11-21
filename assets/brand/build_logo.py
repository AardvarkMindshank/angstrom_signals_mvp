"""MarketNavi logo set: vector lockups (text as outlines, Poppins), icons and favicons."""
import re
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

FONTS = "/usr/share/fonts/truetype/google-fonts/"
GOLD = '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F4CD66"/><stop offset="1" stop-color="#C38B25"/></linearGradient>'
TEAL, NAVY, RED = "#19D3B5", "#0B1B36", "#EF4444"
TEAL_TEXT_LIGHT = "#0FA98F"     # the .ai on white (the bright teal is too pale on white)
mark_body = re.search(r"</defs>(.*)</svg>", open("mark.svg").read(), re.S).group(1)

def text_path(text, font_file, size, x, y, spacing=0.0):
    f = TTFont(FONTS + font_file); gs = f.getGlyphSet(); cmap = f.getBestCmap(); upm = f["head"].unitsPerEm
    s = size / upm; out = []; cx = x
    for ch in text:
        name = cmap[ord(ch)]; pen = SVGPathPen(gs)
        gs[name].draw(TransformPen(pen, (s, 0, 0, -s, cx, y)))
        out.append(pen.getCommands()); cx += gs[name].width * s + spacing * size
    return " ".join(out), cx - x

SAIL = ('<path fill="url(#g)" d="M106 40 C126 68 144 102 152 136 L104 136 C110 105 110 72 106 40 Z"/>'
        '<path fill="url(#g)" d="M96 64 C92 93 81 117 63 136 L96 136 C99 113 99 89 96 64 Z"/>'
        f'<path fill="{TEAL}" d="M40 154 C88 136 136 130 170 134 C135 141 92 150 56 162 Z"/>')

def lockup(dark: bool, tagline=True):
    ink = "#FFFFFF" if dark else NAVY
    ai = TEAL if dark else TEAL_TEXT_LIGHT
    w1, wid1 = text_path("MarketNavi", "Poppins-Bold.ttf", 92, 0, 0)
    w2, wid2 = text_path(".ai", "Poppins-Bold.ttf", 92, wid1, 0)
    total = wid1 + wid2
    t, widt = text_path("AI-POWERED MARKET NAVIGATION", "Poppins-Medium.ttf", 24.5, 0, 0, spacing=0.16)
    W = max(total, widt) + 80
    ox = (W - total) / 2; tx = (W - widt) / 2
    H = 466 if tagline else 410
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H}"><defs>{GOLD}</defs>'
            f'<g transform="translate({W/2-180:.1f},-22) scale(1.8)">{mark_body}</g>'
            f'<g transform="translate({ox:.1f},392)"><path fill="{ink}" d="{w1}"/><path fill="{ai}" d="{w2}"/></g>'
            + (f'<g transform="translate({tx:.1f},446)"><path fill="{ink}" d="{t}"/></g>' if tagline else "") + "</svg>")

def wordmark_row(dark: bool):
    """Mark beside the name, for the app header and emails."""
    ink = "#FFFFFF" if dark else NAVY; ai = TEAL if dark else TEAL_TEXT_LIGHT
    w1, wid1 = text_path("MarketNavi", "Poppins-Bold.ttf", 108, 0, 0)
    w2, wid2 = text_path(".ai", "Poppins-Bold.ttf", 108, wid1, 0)
    W = 202 + wid1 + wid2 + 10
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} 220"><defs>{GOLD}</defs>'
            f'<g transform="translate(-40,-12) scale(1.22)">{SAIL}</g>'
            f'<g transform="translate(200,146)"><path fill="{ink}" d="{w1}"/><path fill="{ai}" d="{w2}"/></g></svg>')

def icon(bg):
    rect = f'<rect width="200" height="200" rx="44" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><defs>{GOLD}</defs>{rect}<g transform="translate(8,-2)">{SAIL}</g></svg>'

def favicon():
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="30 30 150 150"><defs>{GOLD}</defs>{SAIL}</svg>'

files = {"marketnavi-logo-dark.svg": lockup(True), "marketnavi-logo-light.svg": lockup(False),
         "marketnavi-wordmark-dark.svg": wordmark_row(True), "marketnavi-wordmark-light.svg": wordmark_row(False),
         "marketnavi-mark.svg": open("mark.svg").read(),
         "marketnavi-icon-navy.svg": icon(NAVY), "marketnavi-icon-white.svg": icon("#FFFFFF"),
         "marketnavi-favicon.svg": favicon()}
import os
os.makedirs("out", exist_ok=True)
for name, svg in files.items():
    open(f"out/{name}", "w").write(svg)
print("\n".join(files))

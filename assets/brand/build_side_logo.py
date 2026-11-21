"""MarketNavi side-by-side lockup: the emblem on the left, the name and tagline on the right (for the website header)."""
import re
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
F = TTFont("Montserrat-Bold.ttf"); GS = F.getGlyphSet(); CM = F.getBestCmap(); UPM = F["head"].unitsPerEm
def text(s, size, spacing=0.0):
    k = size / UPM; x = 0; out = []
    for ch in s:
        n = CM[ord(ch)]; pen = SVGPathPen(GS); GS[n].draw(TransformPen(pen, (k, 0, 0, -k, x, 0))); out.append(pen.getCommands())
        x += GS[n].width * k + spacing * size
    return " ".join(out), x
for theme, ink, ai in (("light", "#061A32", "#007F73"), ("dark", "#F8F7F2", "#00CDBB")):
    body = re.search(r"</title>(.*)</svg>", open(f"mark-{theme}.svg").read(), re.S).group(1)
    w1, a = text("MarketNavi", 200); w2, b = text(".ai", 200); tg, tw = text("AI-POWERED MARKET NAVIGATION", 61, spacing=0.02)
    x0 = 560; W = x0 + max(a + b, tw) + 20
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} 460" role="img" aria-label="MarketNavi.ai: AI-powered market navigation">'
           f'{body}<g transform="translate({x0} 258)"><path fill="{ink}" d="{w1}"/><g transform="translate({a:.1f} 0)"><path fill="{ai}" d="{w2}"/></g></g>'
           f'<g transform="translate({x0 + 6} 352)"><path fill="{ink}" d="{tg}"/></g></svg>')
    open(f"side-{theme}.svg", "w").write(svg)

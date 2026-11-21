"""GoldNavi logo, in the MarketNavi family: the same compass ring, points, candles and waves, with gold bars in place
of the sails. Text outlined from Montserrat Bold (SIL OFL)."""
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
FONT = "../pack2/Montserrat-Bold.ttf"
C = {"dark": dict(gold="#E8BD54", hi="#F7DC8E", ink="#F8F7F2", teal="#00CDBB", red="#E34B55"),
     "light": dict(gold="#C69420", hi="#E2B850", ink="#061A32", teal="#007F73", red="#E34B55")}

def text(s, size, spacing=0.0):
    f = TTFont(FONT); gs = f.getGlyphSet(); cm = f.getBestCmap(); k = size / f["head"].unitsPerEm; x = 0; out = []
    for ch in s:
        n = cm[ord(ch)]; pen = SVGPathPen(gs); gs[n].draw(TransformPen(pen, (k, 0, 0, -k, x, 0))); out.append(pen.getCommands())
        x += gs[n].width * k + spacing * size
    return " ".join(out), x

def ingot(x, y, c):
    return (f'<path fill="{c["gold"]}" d="M{x} {y} L{x+152} {y} L{x+134} {y-56} L{x+18} {y-56} Z"/>'
            f'<path fill="{c["hi"]}" d="M{x+18} {y-56} L{x+134} {y-56} L{x+120} {y-74} L{x+32} {y-74} Z"/>')

def mark(c):
    return (f'<g fill="none" stroke="{c["gold"]}" stroke-width="7"><path d="M80 181 A184 184 0 0 1 227 48 M285 48 A184 184 0 0 1 433 181 M438 253 A184 184 0 0 1 421 329 M73 253 A184 184 0 0 0 83 308"/></g>'
            f'<g fill="{c["gold"]}"><path d="M256 0 L236 79 L276 79 Z"/><path d="M8 224 L88 205 L88 243 Z"/><path d="M504 224 L424 205 L424 243 Z"/></g>'
            + ingot(100, 372, c) + ingot(262, 372, c) + ingot(181, 290, c)
            + f'<g transform="translate(57 63) scale(.76)"><path fill="{c["gold"]}" d="M36 414 C152 433 286 335 452 370 C325 356 182 462 36 414 Z"/>'
            f'<path fill="{c["teal"]}" d="M45 438 C153 463 295 353 449 408 C318 377 169 485 45 438 Z"/></g>'
            f'<g stroke-width="3"><path stroke="{c["teal"]}" d="M365 159 V226"/><path stroke="{c["teal"]}" stroke-width="17" d="M365 177 V206"/>'
            f'<path stroke="{c["red"]}" d="M390 178 V242"/><path stroke="{c["red"]}" stroke-width="17" d="M390 194 V226"/>'
            f'<path stroke="{c["teal"]}" d="M415 137 V204"/><path stroke="{c["teal"]}" stroke-width="17" d="M415 154 V187"/></g>')

def full(theme):
    c = C[theme]
    w1, a = text("Gold", 150); w2, b = text("Navi", 150)
    tg, tw = text("AI-POWERED GOLD NAVIGATION", 42, spacing=0.03)
    W, H = 1200, 900; ox = (W - a - b) / 2; tx = (W - tw) / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="GoldNavi"><title>GoldNavi</title>'
            f'<g transform="translate({W/2-256*1.05:.1f} 24) scale(1.05)">{mark(c)}</g>'
            f'<g transform="translate({ox:.1f} 700)"><path fill="{c["gold"]}" d="{w1}"/><g transform="translate({a:.1f} 0)"><path fill="{c["ink"]}" d="{w2}"/></g></g>'
            f'<g transform="translate({tx:.1f} 790)"><path fill="{c["ink"]}" d="{tg}"/></g></svg>')

for th in ("dark", "light"):
    open(f"goldnavi-full-{th}.svg", "w").write(full(th))
    open(f"goldnavi-mark-{th}.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 460">{mark(C[th])}</svg>')

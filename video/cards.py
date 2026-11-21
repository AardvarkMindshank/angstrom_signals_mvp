"""Opening and closing cards for training videos, in the style of the sign-in page: the whole MarketNavi logo (name and
"AI-powered market navigation") on white. Writes out/video/intro.png and outro.png (1280 x 720)."""

import json
import os
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path("/usr/share/fonts/truetype/dejavu")
NAVY, GREEN, GREY = (11, 45, 107), (22, 163, 74), (95, 102, 115)
W, H = 1280, 720
WEBSITE, EMAIL = "marketnavi.ai", "info@marketnavi.ai"
COPYRIGHT_LINE = "© {year} Angstrom Signals. MarketNavi is a product of Angstrom Signals."
LOGO = ROOT / "assets" / "brand" / "full-light-tight.png"        # the whole logo, with its name and tagline
BOLD = ROOT / "assets" / "brand" / "Montserrat-Bold.ttf"


def font(size, bold=False):
    if bold and BOLD.exists():
        return ImageFont.truetype(str(BOLD), size)
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def centred(draw, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def card(lines, logo_h) -> Image.Image:
    im = Image.new("RGB", (W, H), "white")
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((round(logo.width * logo_h / logo.height), logo_h), Image.LANCZOS)
    block = logo_h + 28 + sum(gap + size for _, size, _, _, gap in lines)
    y = (H - block) // 2
    im.paste(logo, ((W - logo.width) // 2, y), logo)
    y += logo_h + 28
    d = ImageDraw.Draw(im)
    for text, size, bold, colour, gap in lines:
        y += gap
        centred(d, y, text, font(size, bold), colour)
        y += size
    return im


def main(out: Path) -> None:
    script = json.loads(Path(os.environ.get("SCRIPT", ROOT / "video" / "series" / "05-prism-scan.json")).read_text())
    series = [(script["series"], 22, True, GREY, 30)] if script.get("series") else []
    card([*series, (script["title"], 36, True, GREEN, 10 if series else 34)], 400).save(out / "intro.png")
    following = [(script["next"], 24, True, GREEN, 30)] if script.get("next") else []
    outro = card([(WEBSITE, 34, True, NAVY, 6),
          (EMAIL, 28, False, GREY, 16),
          ("Descriptive readings, not financial advice.", 18, False, GREY, 36),
          *following], 300 if not following else 260)
    d = ImageDraw.Draw(outro)
    centred(d, H - 34, COPYRIGHT_LINE.format(year=date.today().year), font(14), (140, 146, 156))
    outro.save(out / "outro.png")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "out/video"))

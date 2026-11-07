"""Opening and closing cards for training videos, in the style of the sign-in page: the logo, "angstrom signals"
and the tagline on white. Writes out/video/intro.png and outro.png (1280 x 720)."""

import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path("/usr/share/fonts/truetype/dejavu")
NAVY, GREEN, GREY = (11, 45, 107), (22, 163, 74), (95, 102, 115)
W, H = 1280, 720
WEBSITE, EMAIL = "angstromsignals.com", "info@angstromsignals.com"
COPYRIGHT_HOLDER = "Angstrom Signals"      # change to the legal entity's name once it exists


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def centred(draw, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def card(lines, logo_h) -> Image.Image:
    im = Image.new("RGB", (W, H), "white")
    logo = Image.open(ROOT / "assets" / "logo-light.png").convert("RGBA")
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
    script = json.loads((ROOT / "video" / "script.json").read_text())
    card([("angstrom signals", 58, True, NAVY, 0),
          ("Market sentiment and technical signals, with the crowd alongside.", 22, False, GREY, 14),
          (script["title"], 34, True, GREEN, 40)], 210).save(out / "intro.png")
    outro = card([("angstrom signals", 44, True, NAVY, 0),
          (WEBSITE, 36, True, NAVY, 34),
          (EMAIL, 28, False, GREY, 16),
          ("Descriptive readings, not financial advice.", 18, False, GREY, 36)], 160)
    d = ImageDraw.Draw(outro)
    centred(d, H - 34, f"© {date.today().year} {COPYRIGHT_HOLDER}. All rights reserved.", font(14), (140, 146, 156))
    outro.save(out / "outro.png")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "out/video"))

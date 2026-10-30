"""One look for every email sent to people: a header with the logo, a body, an optional button, a footer.

Email programs ignore most web styling, so this uses a table layout with inline styles only.
Every piece of text passed in must already be HTML-safe (use html.escape on anything typed by a person).
"""
from __future__ import annotations

import html
import re

SITE_URL = "https://angstromsignals.com"
LOGO_URL = "https://angstromsignals.com/logo.png"

_INK = "#0c1b3a"
_NAVY = "#0d2d6e"
_BLUE = "#1d5fd1"
_GREEN = "#0f9d46"
_RED = "#c0392b"
_PAPER = "#f7f9fc"
_RULE = "#d5dce8"
_MUTED = "#4a5876"
_FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_TONES = {"up": _GREEN, "down": _RED, "info": _BLUE}


def alert_tone(message: str) -> str:
    """Green for a rise, red for a fall, blue when it is neither."""
    text = str(message or "").lower()
    if any(word in text for word in ("above", "bullish", "rose", "up ")):
        return "up"
    if any(word in text for word in ("below", "bearish", "fell", "down ")):
        return "down"
    return "info"


def asset_logo(url, size: int = 20) -> str:
    """A small round asset logo to sit before a name. Empty when there is no safe https address.

    Email programs drop most styling, so the image carries its own size and alignment.
    Some programs hide remote pictures until the reader allows them; the name still reads fine.
    """
    address = str(url or "").strip()
    if not address.lower().startswith("https://") or any(ch in address for ch in "\"'<> "):
        return ""
    safe = html.escape(address, quote=True)
    return (
        f'<img src="{safe}" width="{size}" height="{size}" alt="" '
        f'style="width:{size}px;height:{size}px;vertical-align:-4px;border:0;'
        f'border-radius:50%;margin-right:8px;background:#ffffff;">'
    )


def section_title(text: str) -> str:
    """A small heading above a group of rows. Text must already be HTML-safe."""
    return (
        f'<p style="margin:22px 0 8px;font:800 13px/1.3 {_FONT};letter-spacing:.06em;'
        f'text-transform:uppercase;color:{_MUTED};">{text}</p>'
    )


def list_row(title: str, detail: str, tone: str = "info") -> str:
    """One row with a coloured stripe: a bold line and a smaller line. Both must be HTML-safe."""
    accent = _TONES.get(tone, _BLUE)
    return (
        f'<div style="margin:0 0 8px;padding:10px 14px;background:{_PAPER};'
        f'border-left:4px solid {accent};border-radius:4px;">'
        f'<div style="font:700 15px/1.4 {_FONT};color:{_INK};">{title}</div>'
        f'<div style="font:400 14px/1.45 {_FONT};color:{_MUTED};">{detail}</div></div>'
    )


def render_email(
    heading: str,
    paragraphs: list[str],
    *,
    button: tuple[str, str] | None = None,
    callout: str = "",
    tone: str = "info",
    footnote: str = "",
    preheader: str = "",
    extra_html: str = "",
    extra_plain: str = "",
) -> tuple[str, str]:
    """Return (html, plain text). Heading, paragraphs, callout and footnote are HTML-safe strings."""
    accent = _TONES.get(tone, _BLUE)
    body = "".join(
        f'<p style="margin:0 0 16px;font:400 16px/1.55 {_FONT};color:{_INK};">{part}</p>'
        for part in paragraphs
        if part
    )
    box = ""
    if callout:
        box = (
            f'<div style="margin:4px 0 20px;padding:14px 16px;background:{_PAPER};'
            f'border-left:4px solid {accent};border-radius:4px;'
            f'font:600 17px/1.5 {_FONT};color:{_INK};">{callout}</div>'
        )
    action = ""
    if button:
        label, url = button
        safe_url = html.escape(url, quote=True)
        action = (
            f'<p style="margin:8px 0 22px;"><a href="{safe_url}" '
            f'style="display:inline-block;background:{_BLUE};color:#ffffff;text-decoration:none;'
            f'font:700 16px/1 {_FONT};padding:14px 24px;border-radius:6px;">{html.escape(label)}</a></p>'
        )
    note = (
        f'<p style="margin:0 0 6px;font:400 13px/1.5 {_FONT};color:{_MUTED};">{footnote}</p>' if footnote else ""
    )
    hidden = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(preheader)}</div>'
        if preheader
        else ""
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(re.sub('<[^>]+>', '', heading))}</title></head>
<body style="margin:0;padding:0;background:{_PAPER};">{hidden}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{_PAPER};padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid {_RULE};border-radius:10px;overflow:hidden;">
<tr><td style="background:{_NAVY};padding:18px 28px;">
<a href="{SITE_URL}" style="text-decoration:none;color:#ffffff;font:800 20px/1 {_FONT};">
<img src="{LOGO_URL}" width="28" height="30" alt="" style="vertical-align:middle;border:0;margin-right:10px;background:#ffffff;border-radius:5px;padding:3px;">Angstrom Signals</a>
</td></tr>
<tr><td style="padding:30px 28px 10px;">
<h1 style="margin:0 0 18px;font:800 24px/1.25 {_FONT};color:{_INK};">{heading}</h1>
{body}{box}{extra_html}{action}
</td></tr>
<tr><td style="padding:6px 28px 26px;border-top:1px solid {_RULE};">
<p style="margin:16px 0 6px;">{note}</p>
<p style="margin:0;font:400 12px/1.5 {_FONT};color:{_MUTED};">Angstrom Signals is a research tool, not financial advice. Past data is not a forecast, and you can lose money trading.
<a href="{SITE_URL}" style="color:{_MUTED};">angstromsignals.com</a></p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""
    return page, _plain(heading, paragraphs, callout, button, footnote, extra_plain)


def _plain(heading, paragraphs, callout, button, footnote, extra_plain="") -> str:
    lines = [_strip(heading), ""]
    lines += [_strip(part) for part in paragraphs if part]
    if callout:
        lines += ["", _strip(callout)]
    if extra_plain:
        lines += ["", extra_plain.strip()]
    if button:
        lines += ["", f"{button[0]}: {button[1]}"]
    if footnote:
        lines += ["", _strip(footnote)]
    lines += ["", "Angstrom Signals is a research tool, not financial advice.", SITE_URL]
    return "\n".join(lines)


def _strip(value: str) -> str:
    text = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", str(value or ""), flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()

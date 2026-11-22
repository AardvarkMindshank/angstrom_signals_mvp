"""📣 Posts the daily video to MarketNavi's social channels (22 Nov 2026), straight after it is published
(daily-video.yml) or by hand (social-post.yml). Each platform posts only when its secrets are set, so channels are
added one at a time; a platform that fails never stops the others.

  python social_post.py [--day YYYY-MM-DD] [--only telegram,email]

Captions come from the day's video: its words (video/<day>.txt), presenter and date. TikTok is posted by hand until
TikTok approves automatic posting: the "email" platform sends a morning pack with the tall video and a caption."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import requests

import briefing

SITE = "https://marketnavi.ai"
TAGS = {"base": "#markets #stocks #crypto #bitcoin #trading", "tiktok": "#markets #crypto #bitcoin #stocks #trading #fyp"}
DISCLAIMER = "Research, not financial advice."


def _base() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip()


def _get(path: str) -> requests.Response:
    return requests.get(briefing.public_url(_base(), path), timeout=30)


def latest(day: str | None = None) -> tuple[str, dict, str]:
    """(day, its videos.json entry, its words) for the given day, or the newest video."""
    meta = _get("video/videos.json").json()
    day = day or max(meta)
    words = _get(f"video/{day}.txt")
    return day, meta[day], (words.text if words.status_code == 200 else "")


def urls(day: str) -> dict:
    u = lambda n: briefing.public_url(_base(), f"video/{day}_{n}")    # noqa: E731
    return {"tall": u("port.mp4"), "wide": u("land.mp4"), "tall_poster": u("port.jpg"), "wide_poster": u("land.jpg")}


def captions(day: str, entry: dict, words: str) -> dict[str, str]:
    """One caption per platform: the day's headline (the video's first line, after the date), who presents it, the
    link and the disclaimer, sized for each platform."""
    when = datetime.fromisoformat(day).strftime("%a %d %b")
    first = (words.strip().split("\n\n") or [""])[0]
    headline = first.split(". ", 1)[1].strip() if ". " in first else first.strip()
    headline = headline.rstrip(".") + "." if headline else ""
    who = entry.get("presenter") or "the crew"
    long = (f"🧭 MarketNavi daily forecast · {when}\n{headline}\n\n🎙️ Presented by {who}. The tide, stocks and crypto "
            f"in about 90 seconds.\n\n▶️ {SITE}\n{DISCLAIMER}")
    return {
        "telegram": long,
        "facebook": long + "\n\n" + TAGS["base"],
        "instagram": long.replace(f"▶️ {SITE}", "▶️ Link in bio") + "\n\n" + TAGS["base"],
        "threads": f"🧭 {when}: {headline} Presented by {who}. {SITE}"[:480],
        "x": f"🧭 MarketNavi daily forecast · {when}\n{headline}\n\n{SITE} #crypto #stocks"[:270],
        "youtube_title": f"Market forecast {when}: {headline}"[:95],
        "youtube": long + "\n\n" + TAGS["base"],
        "tiktok": f"🧭 {when}: {headline} Presented by {who}. {DISCLAIMER}\n{TAGS['tiktok']}",
    }


# ------------------------------------------------------------------------------------------------ platforms

def post_telegram(day: str, caps: dict, links: dict) -> str:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHANNEL", "").strip()
    if not (token and chat):
        return "skipped (not connected)"
    r = requests.post(f"https://api.telegram.org/bot{token}/sendVideo", timeout=120, data={
        "chat_id": chat, "video": links["tall"], "caption": caps["telegram"][:1000], "supports_streaming": "true",
        "thumbnail": links["tall_poster"]})
    ok = r.ok and r.json().get("ok")
    return "posted" if ok else f"failed (HTTP {r.status_code}: {r.json().get('description', '')[:120] if r.headers.get('content-type','').startswith('application/json') else ''})"


def post_email(day: str, caps: dict, links: dict) -> str:
    """The morning pack for posting by hand (TikTok for now): the tall video and its caption."""
    to = os.getenv("SOCIAL_PACK_TO", "").strip()
    if not (to and os.getenv("RESEND_API_KEY")):
        return "skipped (no address)"
    import beta_worker
    from email_brand import render_email
    when = datetime.fromisoformat(day).strftime("%A %d %B")
    page, plain = render_email(
        f"Today's video is ready: {when}",
        ["It has gone out automatically to the connected channels. For TikTok, download the tall video and paste "
         "this caption:", caps["tiktok"]],
        button=("Download the tall video", links["tall"]), tone="info",
        footnote=f"Wide version: {links['wide']}", preheader="The daily video and its TikTok caption.")
    return "sent" if beta_worker._send_resend(to, f"Daily video {when}: TikTok pack", page, plain) else "failed"


PLATFORMS = {"telegram": post_telegram, "email": post_email}


def main() -> int:
    a = sys.argv
    day = a[a.index("--day") + 1] if "--day" in a else None
    only = set(a[a.index("--only") + 1].split(",")) if "--only" in a else set(PLATFORMS)
    day, entry, words = latest(day)
    caps, links = captions(day, entry, words), urls(day)
    for name, post in PLATFORMS.items():
        if name not in only:
            continue
        try:
            print(f"{name}: {post(day, caps, links)}", flush=True)
        except Exception as exc:
            print(f"{name}: failed ({type(exc).__name__})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

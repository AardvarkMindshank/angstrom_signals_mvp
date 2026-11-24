"""📣 Posts the daily video to MarketNavi's social channels (22 Nov 2026), straight after it is published
(daily-video.yml) or by hand (social-post.yml). Each platform posts only when its secrets are set, so channels are
added one at a time; a platform that fails never stops the others.

  python social_post.py [--day YYYY-MM-DD] [--only telegram,email]

Captions come from the day's video: its words (video/<day>.txt), presenter and date. TikTok is posted by hand until
TikTok approves automatic posting: the "email" platform sends a morning pack with the tall video and a caption."""
from __future__ import annotations

import json
import os
import time
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
    """A fresh copy, never a cached one: the index is read seconds after the new video is uploaded (23 Nov 2026 the
    cached index still named Sunday, so Sunday's video went out on Monday)."""
    return requests.get(briefing.public_url(_base(), path), params={"fresh": str(int(time.time()))},
                        headers={"Cache-Control": "no-cache"}, timeout=30)


def latest(day: str | None = None) -> tuple[str, dict, str]:
    """(day, its videos.json entry, its words) for the given day, or the newest video."""
    meta = _get("video/videos.json").json()
    day = day or max(meta)
    words = _get(f"video/{day}.txt")
    return day, meta[day], (words.text if words.status_code == 200 else "")


def urls(day: str, made_at=None) -> dict:
    """The day's files. With the video's made_at, each link carries its version, so a platform that fetches by link
    (Telegram) or a CDN never hands out an earlier copy of a re-made video (23 Nov 2026: Telegram posted the earlier
    cat video under the new Captain caption)."""
    stamp = "".join(ch for ch in str(made_at or "") if ch.isdigit())[:14]
    u = lambda n: briefing.public_url(_base(), f"video/{day}_{n}") + (f"?v={stamp}" if stamp else "")    # noqa: E731
    return {"tall": u("port.mp4"), "wide": u("land.mp4"), "tall_poster": u("port.jpg"), "wide_poster": u("land.jpg")}


def captions(day: str, entry: dict, words: str) -> dict[str, str]:
    """One caption per platform: the day's headline (the video's first line, after the date), who presents it, the
    link and the disclaimer, sized for each platform."""
    when = datetime.fromisoformat(day).strftime("%a %d %b")
    first = (words.strip().split("\n\n") or [""])[0]
    headline = first.split(". ", 1)[1].strip() if ". " in first else first.strip()
    headline = headline.rstrip(".") + "." if headline else ""
    who = entry.get("presenter") or "the crew"
    long = (f"🧭 MarketNavi Morning Outlook · {when}\n{headline}\n\n🎙️ Presented by {who}. The tide, stocks and crypto "
            f"in about 90 seconds.\n\n▶️ {SITE}\n{DISCLAIMER}")
    return {
        "telegram": long,
        "facebook": long + "\n\n" + TAGS["base"],
        "instagram": long.replace(f"▶️ {SITE}", "▶️ Link in bio") + "\n\n" + TAGS["base"],
        "threads": f"🧭 {when}: {headline} Presented by {who}. {SITE}"[:480],
        "x": f"🧭 MarketNavi Morning Outlook · {when}\n{headline}\n\n{SITE} #crypto #stocks"[:270],
        "youtube_title": f"Morning Outlook {when}: {headline}"[:95],
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


def download_link(url: str, name: str) -> str:
    """The link that saves the file instead of playing it in the browser (storage's download option; 23 Nov 2026: the
    email's button only played the video)."""
    return url + ("&" if "?" in url else "?") + "download=" + name


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
        button=("Download the tall video", download_link(links["tall"], f"MarketNavi-{day}-tall.mp4")), tone="info",
        footnote=f"Wide version: {links['wide']}", preheader="The daily video and its TikTok caption.")
    return "sent" if beta_worker._send_resend(to, f"Daily video {when}: TikTok pack", page, plain) else "failed"


def _youtube_token() -> str:
    cid, sec, ref = (os.getenv(k, "").strip() for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"))
    if not (cid and sec and ref):
        return ""
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"})
    if not r.ok:
        raise RuntimeError(f"Google sign-in refused (HTTP {r.status_code}: {r.json().get('error', '')})")
    return r.json()["access_token"]


def _youtube_upload(token: str, video_url: str, title: str, description: str, tags: list[str]) -> str:
    data = requests.get(video_url, timeout=120).content
    meta = {"snippet": {"title": title, "description": description, "tags": tags, "categoryId": "27"},   # Education
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True}}
    start = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                          json=meta, timeout=60, headers={"Authorization": f"Bearer {token}",
                                                          "X-Upload-Content-Type": "video/mp4",
                                                          "X-Upload-Content-Length": str(len(data))})
    if not start.ok:
        raise RuntimeError(f"YouTube refused the upload (HTTP {start.status_code}: {start.text[:160]})")
    done = requests.put(start.headers["Location"], data=data, timeout=600, headers={"Content-Type": "video/mp4"})
    if not done.ok:
        raise RuntimeError(f"YouTube upload failed (HTTP {done.status_code}: {done.text[:160]})")
    body = done.json()
    return f"{body['id']} ({body.get('status', {}).get('privacyStatus', '?')})"


def post_youtube(day: str, caps: dict, links: dict) -> str:
    """The wide video as a normal upload and the tall one as a Short. Until YouTube approves the project (its API
    audit), YouTube keeps uploads from it private."""
    token = _youtube_token()
    if not token:
        return "skipped (not connected)"
    tags = ["market outlook", "crypto", "stocks", "bitcoin", "trading", "MarketNavi"]
    wide = _youtube_upload(token, links["wide"], caps["youtube_title"], caps["youtube"], tags)
    tall = _youtube_upload(token, links["tall"], (caps["youtube_title"][:88] + " #Shorts"), caps["youtube"], tags)
    return f"posted: video {wide}, Short {tall}"


def _x_auth(method: str, url: str, query: dict | None = None) -> str:
    """An OAuth 1.0a header for the MarketNavi account (JSON and file bodies are not part of the signature)."""
    import base64
    import hashlib
    import hmac
    import secrets as _s
    import time
    from urllib.parse import quote
    key, sec, tok, tsec = (os.getenv(k, "").strip() for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"))
    o = {"oauth_consumer_key": key, "oauth_nonce": _s.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": tok, "oauth_version": "1.0"}
    q = lambda v: quote(str(v), safe="~")   # noqa: E731
    params = "&".join(f"{q(k)}={q(v)}" for k, v in sorted({**o, **(query or {})}.items()))
    base = "&".join([method.upper(), q(url), q(params)])
    o["oauth_signature"] = base64.b64encode(hmac.new(f"{q(sec)}&{q(tsec)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in sorted(o.items()))


def post_x(day: str, caps: dict, links: dict) -> str:
    """The wide video with a short caption, uploaded in chunks (X's media upload), then posted."""
    import time
    if not all(os.getenv(k, "").strip() for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")):
        return "skipped (not connected)"
    data = requests.get(links["wide"], timeout=120).content
    api = "https://api.x.com/2/media/upload"
    r = requests.post(f"{api}/initialize", timeout=60, headers={"Authorization": _x_auth("POST", f"{api}/initialize")},
                      json={"media_type": "video/mp4", "total_bytes": len(data), "media_category": "tweet_video"})
    if not r.ok:
        me = requests.get("https://api.x.com/2/users/me", timeout=30,
                          headers={"Authorization": _x_auth("GET", "https://api.x.com/2/users/me")})
        who = (me.json().get("data") or {}).get("username", "") if me.ok else ""
        raise RuntimeError(f"X refused the upload (HTTP {r.status_code}); the keys themselves "
                           + (f"work (signed in as @{who})" if who else f"were refused too (HTTP {me.status_code})"))
    mid = r.json()["data"]["id"]
    step = 4 * 1024 * 1024
    for i in range(0, len(data), step):
        url = f"{api}/{mid}/append"
        a = requests.post(url, timeout=120, headers={"Authorization": _x_auth("POST", url)},
                          data={"segment_index": str(i // step)}, files={"media": ("chunk.mp4", data[i:i + step], "video/mp4")})
        if not a.ok:
            raise RuntimeError(f"X upload failed (HTTP {a.status_code}: {a.text[:200]})")
    url = f"{api}/{mid}/finalize"
    f = requests.post(url, timeout=60, headers={"Authorization": _x_auth("POST", url)})
    if not f.ok:
        raise RuntimeError(f"X upload failed at the end (HTTP {f.status_code}: {f.text[:200]})")
    info = (f.json().get("data") or {}).get("processing_info")
    for _ in range(40):
        if not info or info.get("state") in ("succeeded", "failed"):
            break
        time.sleep(int(info.get("check_after_secs") or 3))
        q = {"command": "STATUS", "media_id": mid}
        st = requests.get(api, params=q, timeout=60, headers={"Authorization": _x_auth("GET", api, q)})
        info = (st.json().get("data") or {}).get("processing_info") if st.ok else None
    if info and info.get("state") == "failed":
        raise RuntimeError("X could not process the video")
    t = requests.post("https://api.x.com/2/tweets", timeout=60, json={"text": caps["x"], "media": {"media_ids": [mid]}},
                      headers={"Authorization": _x_auth("POST", "https://api.x.com/2/tweets")})
    if not t.ok:
        raise RuntimeError(f"X refused the post (HTTP {t.status_code}: {t.text[:200]})")
    return f"posted ({t.json()['data']['id']})"


PLATFORMS = {"telegram": post_telegram, "youtube": post_youtube, "x": post_x, "email": post_email}


POST_AT_HOUR = 8                           # 08:00 Bangkok (Angus, 23 Nov 2026): the video is made earlier, posted then
POST_ZONE = "Asia/Bangkok"
POST_FROM = "2026-11-24"                   # the first day posted this way (Monday 23 Nov was handled by hand)


def due(now: datetime | None = None) -> str:
    """Today's day (YYYY-MM-DD, Bangkok) when its video should be posted now: from 08:00, once the video is
    published, and not posted yet. "" otherwise. The 5-minute worker (alerts.yml) asks this."""
    from zoneinfo import ZoneInfo

    local = (now or datetime.now(ZoneInfo(POST_ZONE))).astimezone(ZoneInfo(POST_ZONE))
    if local.hour < POST_AT_HOUR:
        return ""
    day = local.date().isoformat()
    if day < POST_FROM:
        return ""
    try:
        meta = _get("video/videos.json").json()
    except Exception:
        return ""
    if day not in meta or _get(f"video/{day}.posted").status_code == 200:
        return ""
    return day


def claim(day: str) -> bool:
    """Mark the day as posted before anything goes out, so two runs can never post it twice. True when this run
    claimed it; False when another already had (the storage refuses to overwrite the marker)."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    r = requests.post(f"{_base().rstrip('/')}/storage/v1/object/{briefing.BUCKET}/video/{day}.posted",
                      headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "text/plain",
                               "x-upsert": "false"}, data=datetime.now().isoformat().encode(), timeout=30)
    return r.status_code in (200, 201)


def main() -> int:
    a = sys.argv
    if "--due" in a:
        print(due() or "0")
        return 0
    day = a[a.index("--day") + 1] if "--day" in a else None
    only = set(a[a.index("--only") + 1].split(",")) if "--only" in a else set(PLATFORMS)
    if "--claim" in a:
        if not day or not claim(day):
            print(f"{day or 'No day'}: already posted (or no day given); nothing sent.")
            return 0
    day, entry, words = latest(day)
    caps, links = captions(day, entry, words), urls(day, entry.get("made_at"))
    for name, post in PLATFORMS.items():
        if name not in only:
            continue
        try:
            print(f"{name}: {post(day, caps, links)}", flush=True)
        except Exception as exc:
            print(f"{name}: failed ({type(exc).__name__}: {str(exc)[:240]})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
🎧 Makes the morning briefings that are due (briefing.py): every 15 minutes from .github/workflows/briefing.yml.

    python run_briefings.py --check     # prints how many are due (the workflow skips the voice set-up when none)
    python run_briefings.py             # makes them

For each member due: gather the facts, write the script (AI, else a plain one), speak and mix it
(briefing_audio.py), upload <token>/<day>.mp3 and .txt to the "briefings" bucket, rewrite <token>/feed.xml with the
last 14 episodes, delete older ones, email the link if asked, and note the day as made. The repository is public, so
the log names no member and prints no briefing text.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import briefing


def _client():
    from supabase import create_client

    import run_alerts

    url, key = run_alerts.load_credentials()
    return create_client(url, key), url


def _prefs(db) -> list[dict]:
    return (db.table("user_preferences").select("user_id, crypto_watchlist, stock_watchlist, settings")
            .execute().data or [])


def _meta(db, token: str) -> dict:
    try:
        return json.loads(db.storage.from_(briefing.BUCKET).download(f"{token}/episodes.json"))
    except Exception:
        return {}


def due_rows(db, now=None) -> list[dict]:
    """The members whose briefing should be made now. The settings say so (briefing.due); the bucket's own record
    (episodes.json: the days made and when) is the final word, as the app may save an older copy of the settings
    over the worker's note."""
    now = now or datetime.now(timezone.utc)
    out = []
    for p in _prefs(db):
        settings = p.get("settings") if isinstance(p.get("settings"), dict) else {}
        if not briefing.due(settings, now):
            continue
        b = briefing.settings_of(settings)
        if not b.get("token"):
            continue                                   # the app makes the token when the briefing is set up
        meta = _meta(db, b["token"])
        made = max((m.get("made_at") or "" for m in meta.values() if isinstance(m, dict)), default="")
        state = settings.get("briefing_state") if isinstance(settings.get("briefing_state"), dict) else {}
        asked = str(state.get("requested") or "")
        today = briefing.local_now(b["zone"], now).date().isoformat()
        if (asked and asked > made) or (b["on"] and today not in meta
                                        and briefing.local_now(b["zone"], now).hour >= b["hour"]):
            out.append(p)
    return out


def _save_state(db, user_id: str, settings: dict, **changes) -> None:
    """Merge into settings["briefing_state"] / ["briefing"] on the member's row (the worker's service key)."""
    fresh = (db.table("user_preferences").select("settings").eq("user_id", user_id).execute().data or [{}])[0]
    s = fresh.get("settings") if isinstance(fresh.get("settings"), dict) else dict(settings)
    for key, value in changes.items():
        part = dict(s.get(key) or {})
        part.update(value)
        s[key] = part
    db.table("user_preferences").update({"settings": s}).eq("user_id", user_id).execute()


def _episodes(db, url: str, token: str) -> list[dict]:
    """The episodes in the member's folder, newest first: [{day, label, pub, url, bytes, seconds, summary}]."""
    try:
        files = db.storage.from_(briefing.BUCKET).list(token, {"limit": 100}) or []
    except Exception:
        files = []
    days = sorted({f["name"][:-4] for f in files if str(f.get("name", "")).endswith(".mp3")}, reverse=True)
    meta = _meta(db, token)
    out = []
    for day in days:
        m = meta.get(day) or {}
        at = datetime.fromisoformat(day).replace(hour=6, tzinfo=timezone.utc)
        out.append({"day": day, "label": at.strftime("%A %d %B %Y"), "pub": at.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                    "url": briefing.public_url(url, f"{token}/{day}.mp3"), "bytes": m.get("bytes", 0),
                    "seconds": m.get("seconds", 0), "summary": m.get("summary", "")})
    return out


def _upload(db, path: str, data: bytes, kind: str) -> None:
    db.storage.from_(briefing.BUCKET).upload(path, data, {"content-type": kind, "upsert": "true",
                                                         "cache-control": "300"})


def _email(db, user_id: str, day_label: str, listen: str, feed: str) -> None:
    import run_alerts
    from email_brand import render_email

    to = run_alerts.user_email(db, user_id)
    if not to:
        return
    page, plain = render_email(
        "🎧 Your morning briefing is ready",
        [f"Today's briefing, {day_label}, is ready to play.",
         "It summarises the app's readings for the sections and assets you chose. It is not advice."],
        button=("▶️ Listen now", listen),
        footnote=("To get it in a podcast app, add your private feed (Apple Podcasts: Library, then Follow a Show by "
                  f"URL): {feed}. Change the sections, time and voice in the app under 🎧 Morning briefing."),
        preheader="Your morning briefing is ready to play.")
    run_alerts.send_digest_email(to, f"🎧 Your morning briefing, {day_label}", page, plain)


def make_one(db, url: str, row: dict, now: datetime) -> bool:
    import briefing_audio

    user_id = row["user_id"]
    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
    b = briefing.settings_of(settings)
    token = b["token"]
    here = briefing.local_now(b["zone"], now)
    day = here.date().isoformat()
    facts = briefing.gather(db, user_id, row, b, now)
    name = ""
    script, writer = briefing.write_script(db, facts, b, here, name)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / f"{day}.mp3"
        seconds = briefing_audio.make(script, mp3, b["voice"], Path(tmp), weather=briefing.weather(facts))
        data = mp3.read_bytes()
    _upload(db, f"{token}/{day}.mp3", data, "audio/mpeg")
    _upload(db, f"{token}/{day}.txt", script.encode(), "text/plain")
    meta = _meta(db, token)
    meta[day] = {"bytes": len(data), "seconds": round(seconds), "summary": " ".join(script.split()[:40]) + " …",
                 "writer": writer, "made_at": datetime.now(timezone.utc).isoformat()}
    episodes = _episodes(db, url, token)
    old = [e["day"] for e in episodes[briefing.KEEP_EPISODES:]]
    if old:
        try:
            db.storage.from_(briefing.BUCKET).remove([f"{token}/{d}.{x}" for d in old for x in ("mp3", "txt")])
        except Exception:
            pass
        for d in old:
            meta.pop(d, None)
    _upload(db, f"{token}/episodes.json", json.dumps(meta).encode(), "application/json")
    episodes = [e for e in _episodes(db, url, token) if e["day"] not in old]
    feed = briefing.public_url(url, f"{token}/feed.xml")
    _upload(db, f"{token}/feed.xml", briefing.feed_xml(url, token, episodes).encode(), "application/rss+xml")
    state = {"made": day, "requested": None, "last_seconds": round(seconds), "writer": writer, "error": None}
    _save_state(db, user_id, settings, briefing_state=state)
    if b.get("email"):
        try:
            _email(db, user_id, here.strftime("%A %d %B"), briefing.public_url(url, f"{token}/{day}.mp3"), feed)
        except Exception as exc:
            print(f"Briefing email failed: {str(exc)[:120]}")
    print(f"Briefing made: {round(seconds)} s, script by {writer}, {len(data) // 1024} KB")
    return True


def sample(out: str) -> int:
    """A sample episode from today's real readings (markets, the Tide, the week's events, three coins), for trying
    the voice and the style; nothing is saved to any account."""
    import briefing_audio

    db, _url = _client()
    now = datetime.now(timezone.utc)
    prefs = {"crypto_watchlist": {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "solana": "Solana"},
             "stock_watchlist": {}, "settings": {}}
    b = briefing.settings_of({"briefing": {"minutes": 3, "sections": ["markets", "tides", "watchlist", "events"],
                                           "voice": os.getenv("VOICE") or "bf_emma"}})
    facts = briefing.gather(db, "00000000-0000-0000-0000-000000000000", prefs, b, now)
    script, writer = briefing.write_script(db, facts, b, now)
    Path(out).with_suffix(".txt").write_text(script)
    seconds = briefing_audio.make(script, Path(out), b["voice"], weather=briefing.weather(facts))
    print(f"Sample made: {round(seconds)} s, script by {writer}, weather {briefing.weather(facts)}")
    return 0


def main() -> int:
    if "--sample" in sys.argv:
        return sample(sys.argv[sys.argv.index("--sample") + 1])
    db, url = _client()
    now = datetime.now(timezone.utc)
    rows = due_rows(db, now)
    if "--check" in sys.argv:
        print(len(rows))
        out = os.getenv("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as fh:
                fh.write(f"due={len(rows)}\n")
        return 0
    made = 0
    for row in rows:
        try:
            made += make_one(db, url, row, now)
        except Exception as exc:
            print(f"A briefing failed: {type(exc).__name__}: {str(exc)[:200]}")
            try:
                _save_state(db, row["user_id"], row.get("settings") or {}, briefing_state={"requested": None,
                            "error": f"{type(exc).__name__}: {str(exc)[:160]}", "error_at": now.isoformat()})
            except Exception:
                pass
    print(f"Briefings made: {made} of {len(rows)} due")
    return 0


if __name__ == "__main__":
    sys.exit(main())

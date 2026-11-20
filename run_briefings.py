"""
🎧 Makes the spoken briefings that are due (briefing.py): every 15 minutes from .github/workflows/briefing.yml.

    python run_briefings.py --check                 # prints how many are due (the voice is set up only when some are)
    python run_briefings.py                         # makes them
    python run_briefings.py --sample out.mp3 general|passage   # a sample from today's readings, saved nowhere

🌍 The Morning forecast (the same for everyone): each edition once a day (briefing.EDITIONS), under general/ in the
"briefings" bucket, with episodes.json and one shared feed.xml (the last 28 episodes).

🧭 The spoken Passage Plan (Pro and Elite, when switched on or asked for): the member's newest written Passage Plan
from the last 14 hours (navigator.latest_plan), else one written now and saved in their logbook, read aloud, under
<token>/<day>.mp3 and .txt with their private feed. The repository is public, so the log names no member and prints
no briefing text.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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


def general_due(db, now=None) -> list[tuple[str, str]]:
    return briefing.editions_due(_meta(db, briefing.GENERAL), now or datetime.now(timezone.utc))


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
            if briefing.personal_allowed(briefing.plan_of(db, p["user_id"])):
                out.append(p)
            elif asked:
                _save_state(db, p["user_id"], settings, briefing_state={"requested": None,
                            "error": "The spoken Passage Plan comes with Pro and Elite.", "error_at": now.isoformat()})
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
    """The episodes in a folder (a member's token, or general/), newest first:
    [{day, label, title, pub, url, bytes, seconds, summary}]. General ids are "<day>-<edition>"."""
    try:
        files = db.storage.from_(briefing.BUCKET).list(token, {"limit": 200}) or []
    except Exception:
        files = []
    meta = _meta(db, token)
    ids = {f["name"][:-4] for f in files if str(f.get("name", "")).endswith(".mp3")}
    out = []
    for eid in ids:
        m = meta.get(eid) or {}
        day, edition = eid[:10], eid[11:]
        try:
            made = datetime.fromisoformat(str(m.get("made_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            made = datetime.fromisoformat(day).replace(hour=6, tzinfo=timezone.utc)
        label = datetime.fromisoformat(day).strftime("%A %d %B %Y")
        title = (f"Morning forecast, {briefing.EDITIONS[edition]['name']}, {label}"
                 if edition in briefing.EDITIONS else None)
        out.append({"day": eid, "label": label, "title": title, "made": made,
                    "pub": made.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                    "url": briefing.public_url(url, f"{token}/{eid}.mp3"), "bytes": m.get("bytes", 0),
                    "seconds": m.get("seconds", 0), "summary": m.get("summary", "")})
    return sorted(out, key=lambda e: e["made"], reverse=True)


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
        "🧭 Your Passage Plan is ready to play",
        [f"Today's Passage Plan, {day_label}, is ready to play. It is the same plan you can read in your 📓 Logbook, "
         "read aloud.", "It describes the app's readings for your watchlist and funnels. It is not advice."],
        button=("▶️ Listen now", listen),
        footnote=("To get it in a podcast app, add your private feed (Apple Podcasts: Library, then Follow a Show by "
                  f"URL): {feed}. Change the time and voice in the app under 📓 Logbook."),
        preheader="Your Passage Plan is ready to play.")
    run_alerts.send_digest_email(to, f"🧭 Your Passage Plan, {day_label}", page, plain)


def _watchlist(row: dict) -> dict:
    def as_dict(v):
        return v if isinstance(v, dict) else {str(x): str(x) for x in (v or [])}

    return {"crypto": as_dict(row.get("crypto_watchlist")), "stock": as_dict(row.get("stock_watchlist"))}


def _plan_for(db, user_id: str, row: dict, now: datetime) -> tuple[dict, str]:
    """(the written plan to read, who wrote it): the newest from the last 14 hours, else one written now with the AI
    chosen for briefings and saved in the member's logbook."""
    import ai_providers
    import navigator
    import tides

    kept = navigator.latest_plan(db, user_id, now=now)
    if kept:
        return kept, str(kept.get("model") or "logbook")
    provider = ai_providers.pick("briefing", ai_providers.app_choice(db, "briefing"))
    body, used = navigator.write_plan(db, user_id, _watchlist(row), tides.latest(db), provider)
    if not navigator.complete(body):
        raise RuntimeError("the Passage Plan came back cut short")
    return {"body": body, "created_at": datetime.now(timezone.utc).isoformat()}, used


def make_one(db, url: str, row: dict, now: datetime) -> bool:
    import briefing_audio

    user_id = row["user_id"]
    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
    b = briefing.settings_of(settings)
    token = b["token"]
    here = briefing.local_now(b["zone"], now)
    day = here.date().isoformat()
    plan, writer = _plan_for(db, user_id, row, now)
    script = briefing.spoken_plan(plan["body"], here)
    facts = briefing.gather(db, user_id, row, {"sections": ["markets", "tides"], "assets": []}, now)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / f"{day}.mp3"
        seconds = briefing_audio.make(script, mp3, b["voice"], Path(tmp), weather=briefing.weather(facts))
        data = mp3.read_bytes()
    _upload(db, f"{token}/{day}.mp3", data, "audio/mpeg")
    _upload(db, f"{token}/{day}.txt", script.encode(), "text/plain")
    meta = _meta(db, token)
    meta[day] = {"bytes": len(data), "seconds": round(seconds), "summary": " ".join(script.split()[:40]) + " …",
                 "writer": writer, "plan_at": plan.get("created_at"), "made_at": datetime.now(timezone.utc).isoformat()}
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
    print(f"Passage Plan spoken: {round(seconds)} s, plan by {writer}, {len(data) // 1024} KB")
    return True


def make_general(db, url: str, edition: str, eid: str, now: datetime) -> bool:
    """One edition of the Morning forecast, shared by everyone."""
    import briefing_audio

    folder = briefing.GENERAL
    day = datetime.fromisoformat(eid[:10])
    facts = briefing.general_facts(db, now)
    script, writer = briefing.write_general(db, facts, edition, day)
    weather = briefing.weather(facts)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / f"{eid}.mp3"
        seconds = briefing_audio.make(script, mp3, "bf_emma", Path(tmp), weather=weather)
        data = mp3.read_bytes()
    _upload(db, f"{folder}/{eid}.mp3", data, "audio/mpeg")
    _upload(db, f"{folder}/{eid}.txt", script.encode(), "text/plain")
    meta = _meta(db, folder)
    meta[eid] = {"bytes": len(data), "seconds": round(seconds), "summary": " ".join(script.split()[:40]) + " …",
                 "writer": writer, "edition": edition, "weather": weather,
                 "made_at": datetime.now(timezone.utc).isoformat()}
    episodes = _episodes(db, url, folder)
    old = [e["day"] for e in episodes[briefing.KEEP_GENERAL:]]
    if old:
        try:
            db.storage.from_(briefing.BUCKET).remove([f"{folder}/{d}.{x}" for d in old for x in ("mp3", "txt")])
        except Exception:
            pass
        for d in old:
            meta.pop(d, None)
    _upload(db, f"{folder}/episodes.json", json.dumps(meta).encode(), "application/json")
    episodes = [e for e in _episodes(db, url, folder) if e["day"] not in old]
    _upload(db, f"{folder}/feed.xml", briefing.feed_xml(
        url, "general", episodes, title="Angstrom Signals Morning forecast",
        about="The Angstrom Signals Morning forecast: the main markets, the top coins, the Tide and the week's events, "
              "twice a day. A summary of the app's readings, not advice.", item="Morning forecast").encode(),
        "application/rss+xml")
    print(f"Morning forecast made: {edition}, {round(seconds)} s, script by {writer}, weather {weather}")
    return True


def sample(out: str, kind: str = "general") -> int:
    """A sample from today's real readings, saved to no account: "general" (the Morning forecast, the edition due
    next) or "passage" (a Passage Plan for a made-up member watching three coins, not saved)."""
    import ai_providers
    import briefing_audio
    import navigator
    import tides

    db, _url = _client()
    now = datetime.now(timezone.utc)
    voice = os.getenv("VOICE") or "bf_emma"
    if kind == "passage":
        watch = {"crypto": {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "solana": "Solana"}, "stock": {"NVDA": "NVIDIA"}}
        provider = ai_providers.pick("briefing", ai_providers.app_choice(db, "briefing"))
        body, writer = navigator.write_plan(db, "00000000-0000-0000-0000-000000000000", watch, tides.latest(db),
                                            provider, save=False)
        Path(out).with_suffix(".plan.md").write_text(body)
        script = briefing.spoken_plan(body, now)
        facts = briefing.gather(db, "", {"settings": {}}, {"sections": ["markets", "tides"], "assets": []}, now)
    else:
        edition = "west" if 3 <= now.hour < 15 else "east"
        facts = briefing.general_facts(db, now)
        script, writer = briefing.write_general(db, facts, edition, briefing.local_now(
            briefing.EDITIONS[edition]["zone"], now + timedelta(hours=6)))
        Path(out).with_suffix(".facts.json").write_text(json.dumps(facts, default=str, indent=1))
    Path(out).with_suffix(".txt").write_text(script)
    seconds = briefing_audio.make(script, Path(out), voice, weather=briefing.weather(facts))
    print(f"Sample made ({kind}): {round(seconds)} s, script by {writer}, weather {briefing.weather(facts)}")
    return 0


def main() -> int:
    if "--sample" in sys.argv:
        i = sys.argv.index("--sample")
        return sample(sys.argv[i + 1], sys.argv[i + 2] if len(sys.argv) > i + 2 else "general")
    db, url = _client()
    now = datetime.now(timezone.utc)
    rows = due_rows(db, now)
    editions = general_due(db, now)
    if "--check" in sys.argv:
        print(len(rows) + len(editions))
        out = os.getenv("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as fh:
                fh.write(f"due={len(rows) + len(editions)}\n")
        return 0
    for edition, eid in editions:
        try:
            make_general(db, url, edition, eid, now)
        except Exception as exc:
            print(f"The Morning forecast failed ({edition}): {type(exc).__name__}: {str(exc)[:200]}")
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
    print(f"Passage Plans spoken: {made} of {len(rows)} due")
    return 0


if __name__ == "__main__":
    sys.exit(main())

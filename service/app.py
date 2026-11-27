"""MarketNavi data service (27 Nov 2026): the few things the new app (marketnavi.ai/new/) can't do in the browser,
because they need the Python engine or the AI keys. It runs the same code as the classic app, so the answers match.

    GET  /health                    is it up
    GET  /asset/sets?key=…          the member's own Sets checked on one asset right now (Yes / No / Unknown + why)
    POST /sonar                     the Sonar strip for the candles the chart is showing
    GET  /chart/options?key=…       what the Pro chart can offer for one asset (indicators, Sonar markers, Sets)
    GET  /snapshot?lang=…&save=…    Quick Snapshot: Tides card, what changed, Trend extremes, moods, funnels, markets
    GET  /tides?range=…             the Tides page: the sea drawing, the note, storm warnings, the waves and the currents
    GET  /signals?market=…          a Signals table: your watchlist or a funnel's assets, with every column
    GET  /signals/columns           what the table's column chooser can offer
    POST /chart                     the Pro chart: the classic chart's data for one candle size, range and set of choices
    GET  /search?q=…                news, assets and the member's Logbook that mention a topic ("inflation", "ETF")
    GET  /ai                        the AIs the Navigator can use (for Settings)
    POST /navigator                 the AI Navigator: a question, the conversation so far, what is on screen

Every call needs the member's own sign-in (their Supabase access token): the service reads the database as that
member, so the row rules decide what it can see, exactly as in the app. It holds no member data between calls
beyond short-lived caches, and logs only counts and timings, never questions, answers, names or amounts.

Environment: SUPABASE_URL, SUPABASE_ANON_KEY, ANTHROPIC_API_KEY (and the other AI keys the classic app uses),
ALLOWED_ORIGINS (comma-separated; default https://marketnavi.ai).
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import Depends, FastAPI, Header, HTTPException, Query            # noqa: E402
from fastapi.middleware.cors import CORSMiddleware                           # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware                           # noqa: E402
from pydantic import BaseModel, Field                                        # noqa: E402

app = FastAPI(title="MarketNavi data service", docs_url=None, redoc_url=None)
ORIGINS = [o.strip() for o in (os.environ.get("ALLOWED_ORIGINS") or "https://marketnavi.ai").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], max_age=3600)
app.add_middleware(GZipMiddleware, minimum_size=2000)      # the Pro chart's data shrinks about six times


# ---- who is asking -------------------------------------------------------------------------------------------------

class Member:
    def __init__(self, user_id: str, db, token: str):
        self.id, self.db, self.token = user_id, db, token


_seen: dict = {}            # token → (user id, when checked); a token is re-checked every 5 minutes


def _client(token: str):
    from supabase import create_client

    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(503, "The service isn't set up yet.")
    db = create_client(url, key)
    db.postgrest.auth(token)          # read as the member: the row rules apply
    return db


def member(authorization: str = Header("")) -> Member:
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(401, "Sign in first.")
    db = _client(token)
    hit = _seen.get(token)
    if hit and time.time() - hit[1] < 300:
        return Member(hit[0], db, token)
    try:
        got = db.auth.get_user(token)
        uid = got.user.id if got and got.user else None
    except Exception:
        uid = None
    if not uid:
        raise HTTPException(401, "Your sign-in has expired. Please sign in again.")
    if len(_seen) > 5000:
        _seen.clear()
    _seen[token] = (uid, time.time())
    return Member(uid, db, token)


def _parse_key(key: str) -> tuple[str, str]:
    kind, _, aid = str(key or "").partition("|")
    if kind not in ("Crypto", "Stock") or not aid or len(aid) > 80:
        raise HTTPException(400, "Unknown asset.")
    return ("crypto" if kind == "Crypto" else "equity"), aid


class Cache:
    def __init__(self, ttl: float, size: int = 500):
        self.ttl, self.size, self.data, self.lock = ttl, size, {}, threading.Lock()

    def get(self, key):
        with self.lock:
            hit = self.data.get(key)
            return hit[1] if hit and time.time() - hit[0] < self.ttl else None

    def put(self, key, value):
        with self.lock:
            if len(self.data) >= self.size:
                self.data.pop(next(iter(self.data)))
            self.data[key] = (time.time(), value)
        return value


@app.on_event("startup")
def _warm_up():
    """Load the heavy calculation modules behind the scenes as soon as the service starts, so the first member to
    open a table or a chart doesn't wait for Python to import them (25 Nov 2026: a cold table took 25 seconds)."""
    def warm():
        started = time.time()
        for name in ("pandas", "scoring", "signals_view", "group_readings", "stored_readings", "signal_groups", "prism",
                     "table_columns", "funnel_view", "funnel_runner", "market_store", "lw_chart", "chart_candles",
                     "chart_indicators", "tides", "tides_view", "macro_calendar", "market_overview", "perspectives"):
            try:
                __import__(name)
            except Exception as exc:
                print(f"warm-up: {name} failed ({type(exc).__name__})", flush=True)
        print(f"warm-up: modules loaded in {time.time() - started:.1f}s", flush=True)
    threading.Thread(target=warm, daemon=True).start()


@app.get("/health")
def health():
    return {"ok": True, "at": datetime.now(timezone.utc).isoformat()}


# ---- the member's Sets on one asset --------------------------------------------------------------------------------

SETS_MAX = 12
_sets_cache = Cache(600)


def saved_configs(db) -> list[dict]:
    import signal_groups_inspector as gi

    saved, _ = gi.saved_configs(db)
    return saved or []


@app.get("/asset/sets")
def asset_sets(key: str = Query(...), who: Member = Depends(member)):
    kind, aid = _parse_key(key)
    cached = _sets_cache.get((who.id, key))
    if cached is not None:
        return cached
    import prism
    import signal_library as sl
    from signal_library import loaders

    started = time.time()
    own = [c for c in saved_configs(who.db) if c.get("kind") == "set" and c.get("owner_id") == who.id]
    out = []
    ctx = lambda k, i: sl.DataContext(k, i, derivatives_loader=loaders.derivatives_loader(who.db),     # noqa: E731
                                      sentiment_loader=loaders.sentiment_loader(who.db),
                                      options_loader=loaders.options_loader(who.db))
    market = lambda scope: sl.DataContext("market", scope.split(":", 1)[1],                             # noqa: E731
                                          flows_loader=loaders.flows_loader(who.db),
                                          sentiment_loader=loaders.sentiment_loader(who.db))
    for c in own[:SETS_MAX]:
        doc = c["versions"][-1]["body"]
        try:
            rows = prism.run_now(doc, [(kind, aid, aid)], live_context=ctx, market_context=market)
            r = rows[0] if rows else {}
            out.append({"id": c["id"], "name": c.get("name") or doc.get("name"), "answer": r.get("answer", "unknown"),
                        "why": r.get("reason") or "", "how_sure": r.get("how_sure") or "",
                        "lines": r.get("lines") or {}})
        except Exception as exc:
            out.append({"id": c["id"], "name": c.get("name") or doc.get("name"), "answer": "unknown",
                        "why": str(exc)[:200], "how_sure": "", "lines": {}})
    print(f"sets: {len(out)} checked in {time.time() - started:.1f}s", flush=True)
    return _sets_cache.put((who.id, key), {"sets": out, "more": max(0, len(own) - SETS_MAX),
                                           "at": datetime.now(timezone.utc).isoformat()})


# ---- Sonar for the candles on screen ---------------------------------------------------------------------------------

class Candles(BaseModel):
    time: list[int] = Field(..., max_length=3000)
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


@app.post("/sonar")
def sonar(c: Candles, who: Member = Depends(member)):
    import pandas as pd

    import chart_indicators as ci

    n = len(c.time)
    if n < 40 or any(len(x) != n for x in (c.open, c.high, c.low, c.close, c.volume)):
        raise HTTPException(400, "Not enough candles.")
    df = pd.DataFrame({"open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume},
                      index=pd.to_datetime(c.time, unit="s", utc=True))
    mc = ci.cipher_b(df)
    clean = lambda s: [None if pd.isna(v) else round(float(v), 3) for v in s]                    # noqa: E731
    flags = lambda s: [bool(v) if not pd.isna(v) else False for v in s]                          # noqa: E731
    return {"time": c.time, "wt1": clean(mc["mc_wt1"]), "wt2": clean(mc["mc_wt2"]), "mf": clean(mc["mc_mf"]),
            "buy": flags(mc["mc_buy"]), "sell": flags(mc["mc_sell"]), "cross": [int(v or 0) for v in mc["mc_cross"]]}


# ---- 📸 Quick Snapshot -----------------------------------------------------------------------------------------------

_snap_cache = Cache(45, 2000)


@app.get("/snapshot")
def snapshot(lang: str = Query("en", max_length=8), save: bool = Query(False), who: Member = Depends(member)):
    """Every part of Quick Snapshot. save=true (the first look of a browser session) keeps this visit's readings and
    Candidates as the account's last visit, as the classic page does once a session."""
    from service import snapshot as snap

    if not save:
        hit = _snap_cache.get((who.id, lang))
        if hit is not None:
            return hit
    return _snap_cache.put((who.id, lang), snap.build(who.db, who.id, lang, save))


# ---- 🌊 Tides ----------------------------------------------------------------------------------------------------------

_tides_cache = Cache(300, 200)


@app.get("/tides")
def tides(lang: str = Query("en", max_length=8), range: str = Query("1Y", max_length=3), who: Member = Depends(member)):
    from service import tides_page

    hit = _tides_cache.get((lang, range))
    return hit if hit is not None else _tides_cache.put((lang, range), tides_page.build(who.db, lang, range))


# ---- ₿ 📈 the Signals tables ----------------------------------------------------------------------------------------------

_signals_cache = Cache(60, 2000)


@app.get("/signals")
def signals(market: str = Query(..., pattern="^(crypto|equity)$"), lang: str = Query("en", max_length=8),
            mode: str | None = Query(None, pattern="^(watchlist|funnel)$"), pick: str | None = Query(None, max_length=60),
            stage: str | None = Query(None, max_length=30), fresh: bool = Query(False), who: Member = Depends(member)):
    from service import signals as sig

    key = (who.id, market, lang, mode, pick, stage)
    hit = None if fresh else _signals_cache.get(key)
    return hit if hit is not None else _signals_cache.put(key, sig.build(who.db, who.id, market, lang, mode, pick, stage))


@app.get("/signals/columns")
def signal_columns(lang: str = Query("en", max_length=8), who: Member = Depends(member)):
    from service import signals as sig

    return sig.column_options(who.db, who.id, lang)


# ---- the Pro chart (the classic chart's data, built as the classic app builds it) --------------------------------------

class ChartAsk(BaseModel):
    key: str = Field(..., max_length=90)
    interval: str = Field("1D", max_length=4)
    range: str = Field("3M", max_length=4)
    indicators: list[str] = Field(default_factory=list, max_length=20)
    overlay: bool = False
    sonar_marks: list[str] | None = Field(None, max_length=12)
    dot_buildup: bool = False
    earnings: bool = True
    events: bool = True
    band: str | None = Field(None, max_length=80)
    band_no: bool = False
    dark: bool = False
    price_px: int = 460
    lang: str = Field("en", max_length=8)
    title: str = Field("", max_length=120)


def _asset_type(key: str) -> tuple[str, str]:
    kind, aid = _parse_key(key)
    return ("Crypto" if kind == "crypto" else "Stock"), aid


@app.get("/chart/options")
def chart_options(key: str = Query(...), lang: str = Query("en", max_length=8), who: Member = Depends(member)):
    from service import pro_chart as pro

    asset_type, _ = _asset_type(key)
    return pro.options(who.db, who.id, asset_type, lang)


@app.post("/chart")
def chart(ask: ChartAsk, who: Member = Depends(member)):
    from service import pro_chart as pro

    asset_type, aid = _asset_type(ask.key)
    started = time.time()
    out = pro.payload(who.db, who.id, asset_type, aid, ask, ask.lang, ask.title)
    n = len(((out.get("payload") or {}).get("times")) or [])
    print(f"chart: {ask.interval}/{ask.range} {n} candles in {time.time() - started:.1f}s", flush=True)
    return out


# ---- topic search across the news and the member's Logbook -------------------------------------------------------------

_news = {"at": 0.0, "items": [], "lock": threading.Lock()}
NEWS_TTL = 900


def _load_news(db) -> list[dict]:
    """Every scored headline the app holds: each asset's and each market's news, about 8 per subject."""
    items = []
    page = 0
    while True:
        rows = (db.table("asset_market").select("asset_key,sentiment_report").not_.is_("sentiment_report", "null")
                .order("asset_key").range(page * 500, page * 500 + 499).execute().data or [])
        for r in rows:
            for h in ((r.get("sentiment_report") or {}).get("headlines") or []):
                items.append({**_headline(h), "subject": r["asset_key"]})
        if len(rows) < 500:
            break
        page += 1
    try:
        for r in db.table("market_mood").select("market_key,sentiment_report").execute().data or []:
            for h in ((r.get("sentiment_report") or {}).get("headlines") or []):
                items.append({**_headline(h), "subject": "Market|" + str(r.get("market_key"))})
    except Exception:
        pass
    seen, out = set(), []
    for it in items:
        if it["id"] in seen and it["subject"].startswith("Market|"):
            continue
        seen.add(it["id"])
        out.append(it)
    return out


def _headline(h: dict) -> dict:
    return {"id": str(h.get("id") or h.get("link") or ""), "title": str(h.get("title") or ""), "link": h.get("link"),
            "source": h.get("source") or "", "published_at": h.get("published_at") or "",
            "score": h.get("score"), "note": str(h.get("note") or ""), "tr": h.get("tr") or {}}


def news(db) -> list[dict]:
    with _news["lock"]:
        if time.time() - _news["at"] > NEWS_TTL or not _news["items"]:
            started = time.time()
            _news["items"] = _load_news(db)
            _news["at"] = time.time()
            print(f"news index: {len(_news['items'])} headlines in {time.time() - started:.1f}s", flush=True)
        return _news["items"]


def _terms(q: str) -> list[str]:
    return [w for w in re.findall(r"[\w$€£%.-]+", (q or "").lower()) if len(w) >= 2][:6]


def _hits(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return all(re.search(r"(?<!\w)" + re.escape(t), low) for t in terms)


@app.get("/search")
def search(q: str = Query(..., min_length=2, max_length=80), who: Member = Depends(member)):
    terms = _terms(q)
    if not terms:
        raise HTTPException(400, "Type at least two letters.")
    found = [it for it in news(who.db) if _hits(it["title"] + " " + it["note"], terms)]
    found.sort(key=lambda it: it["published_at"], reverse=True)
    subjects: dict = {}
    for it in found:
        if not it["subject"].startswith("Market|"):
            subjects[it["subject"]] = subjects.get(it["subject"], 0) + 1
    scores = [float(it["score"]) for it in found if it.get("score") is not None]
    logbook = []
    try:
        rows = (who.db.table("navigator_logbook").select("day,kind,body").eq("owner_id", who.id)
                .order("day", desc=True).limit(60).execute().data or [])
        for r in rows:
            body = str(r.get("body") or "")
            m = re.search(r"(?i)(?<!\w)" + re.escape(terms[0]), body)
            if m and _hits(body, terms):
                a, b = max(0, m.start() - 90), min(len(body), m.end() + 110)
                logbook.append({"day": r.get("day"), "kind": r.get("kind") or "", "snippet": body[a:b].strip()})
    except Exception:
        pass
    print(f"search: {len(found)} headlines, {len(logbook)} logbook entries", flush=True)
    return {"q": q, "terms": terms, "news": found[:60], "count": len(found),
            "mood": round(sum(scores) / len(scores), 1) if scores else None,
            "assets": sorted(({"key": k, "articles": n} for k, n in subjects.items()), key=lambda x: -x["articles"])[:12],
            "logbook": logbook[:10]}


# ---- the AI Navigator ------------------------------------------------------------------------------------------------

@app.get("/ai")
def ai_choices(who: Member = Depends(member)):
    """The AIs the Navigator can use here (those with a key on this service), for Settings."""
    import ai_providers as ap

    return {"providers": [{"id": p, "label": ap.label(p)} for p in ap.PROVIDERS if ap.available(p)],
            "default": ap.USES["navigator"][1]}


class Turn(BaseModel):
    role: str
    content: str = Field(..., max_length=20000)


class Question(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[Turn] = Field(default_factory=list, max_length=40)
    language: str = "en"
    start: str = "panel"
    on_screen: str = Field("", max_length=4000)


_asked: dict = {}           # (user id, day) → questions asked today
_plans = Cache(900)


def daily_limit(db, uid: str) -> int:
    import plans

    plan = _plans.get(uid)
    if plan is None:
        try:
            rows = db.table("user_plans").select("plan").eq("user_id", uid).limit(1).execute().data or []
            plan = (rows[0].get("plan") if rows else None) or "pro"
        except Exception:
            plan = "pro"
        _plans.put(uid, plan)
    try:
        return int(plans.LIMITS[plan]["navigator_per_day"])
    except Exception:
        return 25


@app.post("/navigator")
def navigator(q: Question, who: Member = Depends(member)):
    import advisor
    import ai_providers
    import i18n
    import navigator as nav
    import navigator_tools
    import tides

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = _asked.get((who.id, day), 0)
    limit = daily_limit(who.db, who.id)
    if used >= limit:
        raise HTTPException(429, f"limit:{limit}")
    try:
        prefs = who.db.table("user_preferences").select("crypto_watchlist,stock_watchlist,settings") \
            .eq("user_id", who.id).limit(1).execute().data or []
    except Exception:
        prefs = []
    p = prefs[0] if prefs else {}
    watch = {"crypto": p.get("crypto_watchlist") or {}, "stock": p.get("stock_watchlist") or {}}
    provider = ai_providers.pick("navigator", (p.get("settings") or {}).get("ai_navigator"))
    if not ai_providers.available(provider):
        raise HTTPException(503, "The AI Navigator isn't switched on yet.")
    saved = saved_configs(who.db)
    try:
        snap = tides.latest(who.db)
    except Exception:
        snap = None
    try:
        extra = nav.portfolio_context(who.db, who.id, watch)
    except Exception:
        extra = ""
    if q.on_screen.strip():
        extra = (extra + "\n\nOn the person's screen right now: " + q.on_screen.strip()).strip()
    started = time.time()
    with i18n.using(q.language if q.language in i18n.BY_CODE else "en"):
        toolbox = navigator_tools.ToolBox(None, who.db, who.id, saved, watch)
        system = advisor.system_parts(saved, who.id, q.start if q.start in advisor.START else "panel", extra,
                                      market=nav.market_context(snap))
        history = [{"role": t.role, "content": t.content} for t in q.history if t.role in ("user", "assistant")]
        try:
            answer = advisor.ask(history, q.question.strip(), system, provider=provider, tools=toolbox)
        except Exception as exc:
            print(f"navigator: failed after {time.time() - started:.1f}s ({type(exc).__name__})", flush=True)
            raise HTTPException(502, "The Navigator couldn't answer just now. Please try again.")
    _asked[(who.id, day)] = used + 1
    print(f"navigator: answered in {time.time() - started:.1f}s", flush=True)
    return {"answer": answer, "notes": toolbox.notes, "used": used + 1, "limit": limit}

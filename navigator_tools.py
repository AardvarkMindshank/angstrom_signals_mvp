"""
✨ The AI Navigator's tools (19 Nov 2026): instead of only describing, the Navigator can look things up in the app and
prepare a draft Set, through the app's own building blocks and rules (docs/backlog.md, "AI Navigator with tools").

Look (read only):
    find_asset          a coin or company by name or ticker → its id in the app
    asset_readings      an asset's current readings from chosen signals (daily candles unless asked otherwise)
    set_answer          a Set's answer now (Yes / No / Unknown, with the deciding line) for up to 5 assets
    soundings_results   what Soundings found before past rises and falls (crypto or equities)
Build:
    draft_set           a new Set made of single signals and lines; checked by the Set editor's own rules and kept
                        as an unsaved draft that opens in Signal Sets → ➕ New Set. Nothing is saved without the
                        person's click.

Rules the tools keep: no trading or posting; only this person's own Sets and the provided ones; the readings are live
or the saved research results (studies never read the protected hold-out from 30 Oct 2024).
Each tool returns short plain text (JSON where structure helps), so the conversation stays small.
"""

from __future__ import annotations

import json

MAX_ASSETS = 5
DEFAULT_SIGNALS = ("trend.direction", "momentum.direction", "rsi.level", "osc.stoch_rsi", "osc.wavetrend",
                   "sonar.markers", "bollinger.position", "volume.relative", "regime.state", "structure.swings",
                   "tides.tide")

LINE = {"type": "object", "properties": {
    "signal": {"type": "string", "description": "Signal id, e.g. 'osc.stoch_rsi'"},
    "timeframe": {"type": "string", "description": "1D (default), 4h, 1h, 1W …"},
    "params": {"type": "object", "description": "The signal's own settings, if any (e.g. {'current': 'dollar'})"},
    "field": {"type": "string", "description": "The reading, e.g. 'pair' or 'big_green_dot_ago'; '' for the value itself"},
    "op": {"type": "string", "enum": ["gte", "lte", "is", "is_not", "yes", "no", "within", "not_within", "exists"]},
    "value": {"type": ["string", "number"]}},
    "required": ["signal", "field", "op"]}

TOOLS = [
    {"name": "find_asset",
     "description": "Find a coin or a company by name or ticker. Returns matches with their kind (crypto or equity) "
                    "and id, which the other tools take. The person's watchlist is searched first.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "A name or ticker, e.g. 'XRP', 'ripple', 'Apple', 'NVDA'"},
         "kind": {"type": "string", "enum": ["crypto", "equity", "any"], "description": "Which market (default any)"}},
         "required": ["query"]}},
    {"name": "asset_readings",
     "description": "An asset's current readings (live market data, the last finished candle) from chosen signals. "
                    "Give signal ids from the Signals list (e.g. 'osc.stoch_rsi', 'sonar.markers', 'trend.direction'); "
                    "without any, a standard dozen are read. Use it to see what the chart shows now before advising "
                    "how to build or read a Set.",
     "input_schema": {"type": "object", "properties": {
         "asset": {"type": "string", "description": "Name, ticker or id of the asset"},
         "signals": {"type": "array", "items": {"type": "string"}, "description": "Signal ids (optional, up to 12)"},
         "timeframe": {"type": "string", "enum": ["1D", "4h", "1h", "1W"], "description": "Candle size (default 1D)"}},
         "required": ["asset"]}},
    {"name": "set_answer",
     "description": "A Set's answer now for up to 5 assets: Yes, No or Unknown, with the deciding line and its "
                    "readings. The Set is one of the person's own or a provided Set, by its name as listed.",
     "input_schema": {"type": "object", "properties": {
         "set_name": {"type": "string"},
         "assets": {"type": "array", "items": {"type": "string"}, "description": "Names, tickers or ids (1 to 5)"}},
         "required": ["set_name", "assets"]}},
    {"name": "soundings_results",
     "description": "What Soundings found: the conditions that came before past rises or falls more often than "
                    "usual, and whether they held up on later years the search never saw. Research results to "
                    "29 Oct 2024 (the protected test period is never used).",
     "input_schema": {"type": "object", "properties": {
         "market": {"type": "string", "enum": ["crypto", "equity"]},
         "move": {"type": "string", "enum": ["rise", "fall"]}}, "required": ["market", "move"]}},
    {"name": "draft_set",
     "description": "Prepare a new Set from single signals, as an unsaved draft the person opens in Signal Sets "
                    "(Start from: ➕ New Set) to check, change and save. All lines must hold for Yes; an 'any_of' "
                    "box holds when any one of its lines holds. Each line reads one signal's field with an "
                    "operator: gte, lte (numbers), is, is_not (labels), yes, no (yes/no fields), within (a 'candles "
                    "ago' field: in the last N candles). Use the exact signal ids, fields and labels from the "
                    "Signals list. The draft is checked by the editor's own rules; problems come back to fix.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "purpose": {"type": "string", "description": "One sentence"},
         "lines": {"type": "array", "items": LINE},
         "any_of": {"type": "array", "items": {"type": "array", "items": LINE},
                    "description": "Optional OR boxes: each is a list of lines, any one of which is enough"}},
         "required": ["name", "lines"]}},
]


class ToolBox:
    """The tools for one question: who is asking, their saved Groups and Sets, and their watchlist."""

    def __init__(self, st, supabase, user_id: str, saved: list[dict] | None, watchlist: dict | None):
        self.st, self.db, self.user_id = st, supabase, user_id
        self.saved, self.watchlist = saved or [], watchlist or {}
        self.notes: list[str] = []          # what the tools did, shown under the answer (e.g. a draft is ready)

    # ------------------------------------------------------------------ dispatch

    def run(self, name: str, args: dict) -> str:
        try:
            fn = {"find_asset": self.find_asset, "asset_readings": self.asset_readings, "set_answer": self.set_answer,
                  "soundings_results": self.soundings_results, "draft_set": self.draft_set}[name]
        except KeyError:
            return f"Unknown tool {name}."
        try:
            out = fn(**(args or {}))
        except TypeError as exc:
            return f"The tool was called with the wrong inputs ({exc})."
        except Exception as exc:                               # a tool failing must not end the conversation
            return f"The tool failed: {str(exc)[:300]}"
        text = out if isinstance(out, str) else json.dumps(out, default=str, ensure_ascii=False)
        return text[:12000]

    # ------------------------------------------------------------------ look

    def _resolve(self, asset: str, kind: str = "any") -> tuple[str, str, str] | None:
        q = str(asset or "").strip()
        if not q:
            return None
        low = q.lower()
        for k, book in (("crypto", self.watchlist.get("crypto") or {}), ("equity", self.watchlist.get("stock") or {})):
            if kind not in ("any", k):
                continue
            for aid, name in book.items():
                if low in (str(aid).lower(), str(name).lower()) or low == str(name).split(" (")[0].lower() \
                        or f"({low})" in str(name).lower():
                    return k, str(aid), str(name)
        found = self.find_asset(q, kind)
        return (found[0]["kind"], found[0]["id"], found[0]["name"]) if isinstance(found, list) and found else None

    def find_asset(self, query: str, kind: str = "any"):
        import data_fetchers

        out = []
        if kind in ("any", "crypto"):
            try:
                out += [{"kind": "crypto", "id": m["id"], "name": f"{m.get('name') or m['id']} ({m.get('symbol') or ''})"}
                        for m in data_fetchers.search_crypto_matches(query)[:4] if m.get("id")]
            except Exception:
                pass
        if kind in ("any", "equity"):
            try:
                out += [{"kind": "equity", "id": m["symbol"], "name": f"{m.get('name') or m['symbol']} ({m['symbol']})"}
                        for m in data_fetchers.search_stock_matches(query)[:4] if m.get("symbol")]
            except Exception:
                pass
        return out or f"Nothing found for '{query}'."

    def _context(self, kind: str, aid: str):
        import signal_library as sl
        from signal_library import loaders

        return sl.DataContext(kind, aid, derivatives_loader=loaders.derivatives_loader(self.db),
                              sentiment_loader=loaders.sentiment_loader(self.db),
                              options_loader=loaders.options_loader(self.db))

    def asset_readings(self, asset: str, signals: list[str] | None = None, timeframe: str = "1D"):
        import signal_library as sl

        hit = self._resolve(asset)
        if not hit:
            return f"Couldn't find the asset '{asset}'. Try find_asset first."
        kind, aid, name = hit
        latest = {d.id: d for d in sl.REGISTRY.latest()}
        wanted = [s for s in (signals or DEFAULT_SIGNALS) if s in latest][:12]
        unknown = [s for s in (signals or []) if s not in latest]
        refs = []
        for sid in wanted:
            d = latest[sid]
            tf = timeframe if timeframe in d.timeframes else ("1D" if "1D" in d.timeframes else d.timeframes[0])
            refs.append((sid, sl.SignalRef.make(d, tf)))
        got = sl.evaluate([r for _, r in refs], self._context(kind, aid))
        out = {"asset": name, "kind": kind, "id": aid, "readings": {}}
        for sid, ref in refs:
            res = got.get(ref.instance_key)
            if res is None:
                continue
            item = {"status": res.status, "timeframe": ref.timeframe}
            if res.status in ("ok", "stale"):
                item["value"] = _compact(res.value)
                item["as_of"] = res.observed_at
            else:
                item["why"] = "; ".join(res.notes[:2])
            out["readings"][sid] = item
        if unknown:
            out["not_signals"] = unknown
        return out

    def _sets(self) -> dict:
        """name → Set document: the person's own (latest version) and the provided ones."""
        import prism

        out = {}
        for key, doc in prism.demo_sets().items():
            out[doc["name"]] = doc
        for c in self.saved:
            if c.get("kind") == "set" and c.get("owner_id") == self.user_id and c.get("versions"):
                out[c["name"]] = c["versions"][-1]["body"]
        return out

    def set_answer(self, set_name: str, assets: list[str]):
        import prism
        import signal_library as sl
        from signal_library import loaders

        sets = self._sets()
        doc = sets.get(set_name) or next((d for n, d in sets.items() if n.lower() == str(set_name).lower()), None)
        if doc is None:
            close = [n for n in sets if str(set_name).lower() in n.lower()][:8]
            return f"No Set called '{set_name}'." + (f" Did you mean: {', '.join(close)}?" if close else "")
        picked, missing = [], []
        for a in (assets or [])[:MAX_ASSETS]:
            hit = self._resolve(a)
            (picked.append(hit) if hit else missing.append(a))
        if not picked:
            return f"Couldn't find {', '.join(missing)}."
        rows = prism.run_now(
            doc, picked, live_context=self._context,
            market_context=lambda scope: sl.DataContext("market", scope.split(":", 1)[1],
                                                        flows_loader=loaders.flows_loader(self.db),
                                                        sentiment_loader=loaders.sentiment_loader(self.db)))
        out = {"set": doc.get("name"), "answers": [{"asset": r["asset"], "answer": r["answer"], "why": r["reason"]}
                                                   for r in rows]}
        if missing:
            out["not_found"] = missing
        return out

    def soundings_results(self, market: str = "crypto", move: str = "rise"):
        import soundings_view as sv

        report = sv.load(sv.FILES.get(market, sv.FILES["crypto"])[0])
        if not report:
            return "No Soundings results for that market yet."
        part = (report.get("targets") or {}).get(move) or {}
        rows = []
        for r in part.get("results") or []:
            c = r.get("confirm") or {}
            rows.append({"condition": " + ".join(r["condition"]), "verdict": r.get("verdict"),
                         "search_lift": round(r.get("lift") or 0, 2), "later_lift": round(c.get("lift") or 0, 2),
                         "later_assets_better": f"{c.get('coins_up', 0)} of {c.get('coins_read', 0)}",
                         "by_tide": {k: round(v["lift"], 2) for k, v in (r.get("tide_split") or {}).items()
                                     if v.get("lift")}})
        s = report.get("settings") or {}
        return {"market": market, "move": move, "definition": s.get("rise"), "search_years": s.get("search"),
                "later_years": s.get("confirm"), "assets": len(s.get("coins") or []),
                "usual_rate": part.get("base_rate_search"), "results": rows,
                "verdicts": "survivor = held up; either_way = a bigger move either way; fragile = only some assets; "
                            "not_confirmed = weaker later; faded = gone later"}

    # ------------------------------------------------------------------ build

    def draft_set(self, name: str, lines: list[dict], purpose: str = "", any_of: list[list[dict]] | None = None):
        import re

        import drafts as dr
        import lattice_sets as ls

        model = {"name": str(name)[:80], "purpose": str(purpose or "")[:200], "groups": [], "standalone": [],
                 "lines": []}
        keys: dict = {}

        def member(line: dict) -> str:
            sig = str(line.get("signal") or "")
            tf = str(line.get("timeframe") or "1D")
            params = line.get("params") if isinstance(line.get("params"), dict) else {}
            ident = (sig, tf, json.dumps(params, sort_keys=True))
            if ident not in keys:
                base = re.sub(r"[^a-z0-9]+", "_", f"{sig.split('.')[-1]}_{tf}".lower()).strip("_")[:28] or "item"
                key, n = base, 2
                while key in keys.values():
                    key, n = f"{base}_{n}", n + 1
                keys[ident] = key
                entry = {"key": key, "id": sig, "version": 1, "timeframe": tf, "role": "condition"}
                if params:
                    entry["params"] = params
                model["standalone"].append(entry)
            return keys[ident]

        def as_line(line: dict) -> dict:
            value = line.get("value")
            return {"target": "member", "member": member(line), "field": str(line.get("field") or ""),
                    "op": str(line.get("op") or ""), "value": "" if value is None else str(value)}

        for line in lines or []:
            model["lines"].append(as_line(line))
        for box in any_of or []:
            model["lines"].append({"any": [as_line(l) for l in box]})
        clean = ls.clean_model(model, {})
        dropped = len(model["standalone"]) - len(clean["standalone"])
        if dropped:
            known = {s["id"] for s in __import__("lattice_editor").catalogue()}
            bad = [m["id"] for m in model["standalone"] if m["id"] not in known]
            return f"Not built: unknown signal ids {bad}. Use ids from the Signals list."
        problems = ls.checks(clean, {})
        if problems["blocks"]:
            return {"built": False, "problems": problems["blocks"], "warnings": problems["warnings"]}
        dr.remember(self.st.session_state, self.db, self.user_id, "set", "new", clean, ls.empty_model())
        self.notes.append("draft_set")
        return {"built": True, "name": clean["name"], "warnings": problems["warnings"],
                "description": ls.describe(clean, {}),
                "next": "Tell the person: open Angstrom Lattice → Signal Sets → Start from ➕ New Set; the draft opens "
                        "there with a notice. They check it, change it if they like, and save it themselves."}


def _compact(value, depth: int = 0):
    """A signal's value made small for the conversation: long lists cut, floats rounded."""
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _compact(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple)):
        return [_compact(v, depth + 1) for v in list(value)[:6]]
    return value

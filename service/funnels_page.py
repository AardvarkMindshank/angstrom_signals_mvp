"""🔻 The funnel editor for the new app: the classic editor's Python side (funnel_editor.py) as data, the stages board
(funnel_stages_component.py) hosted unchanged in the browser. The browser keeps the working copy (the funnel being
changed) and sends it with each step; this module applies a press to it, checks it, says what a save will change,
and saves through the same database function (funnel_save). Nothing about a member is logged.
"""
from __future__ import annotations

import copy

import i18n


def _ctx(db, uid: str):
    import prism
    from service.lattice import _plan, _saved

    plan, display, settings = _plan(db, uid)
    configs = _saved(db)
    saved_sets = {c["id"]: c for c in configs if c.get("kind") == "set" and str(c.get("owner_id")) == str(uid)}
    return {"plan": plan, "display": display, "show_provided": settings.get("show_provided", True) is not False,
            "configs": configs, "saved_sets": saved_sets, "library": prism.demo_sets()}


def _limit(plan: str) -> int:
    import plans

    return int(plans.LIMITS[plans.normalise(plan)]["funnels"] or 0)


def listing(db, uid: str, lang: str) -> dict:
    """The Funnel pull-down: your own funnels, then the provided ones."""
    import funnel_editor as fe
    import funnel_templates as ft
    import funnel_view as fv
    from service.lattice import _plan

    with i18n.using(lang):
        funnels = fv.load_funnels(db, uid)
        plan, display, _ = _plan(db, uid)
        own = [{"key": f["id"], "name": f["name"], "market": f.get("market") or "crypto", "paused": bool(f.get("paused"))} for f in funnels]
        provided = [{"key": f"new:{k}", "name": ft.FUNNEL_NAMES[k], "kind": k} for k in fe.KINDS]
        return {"own": own, "provided": provided, "limit": _limit(plan), "display": display}


def open_funnel(db, uid: str, key: str, lang: str) -> dict:
    """Your saved funnel as the working copy (and the saved one, to compare against)."""
    import funnel_view as fv

    with i18n.using(lang):
        saved = next((f for f in fv.load_funnels(db, uid) if f["id"] == key), None)
        if not saved:
            return {"status": "error", "message": i18n.t("That funnel no longer exists.")}
        base = copy.deepcopy(saved)
        base.setdefault("pool", {})
        return {"status": "ok", "funnel": base, "saved": saved}


def screen(db, uid: str, f: dict, saved: dict | None, scope: str, lang: str) -> dict:
    """Everything the editor shows for the working copy: its stages board, where it came from, the checks, and what
    saving would change."""
    import funnel_editor as fe
    import funnel_spec as fs
    import funnel_templates as ft

    with i18n.using(lang):
        c = _ctx(db, uid)
        choices = fe.board_choices(c["configs"], uid)
        board = fe.board_data(f, choices, c["library"], c["saved_sets"], c["show_provided"], scope, c["plan"], c["display"])
        with i18n.using("en"):
            badge_en = fe.provenance(f, c["library"])
        badge = fe.provenance(f, c["library"])
        blocks, warns = fs.validate(f)
        what, reset = fe.changes(saved, f)
        market = f.get("market") or "crypto"
        return {"board": board, "badge": i18n.t(badge), "reviewed": badge_en.startswith("Your copy"),
                "earlier": badge_en.startswith("Your copy of an earlier version"),
                "blocks": blocks, "warnings": warns, "changes": [i18n.t(w) for w in what], "reset": reset,
                "unchanged": bool(saved) and not what, "market": market,
                "leave_words": i18n.t('{a_coin_if_market_crypto_} leaves a stage', a_coin_if_market_crypto_='A coin' if market == 'crypto' else 'An equity'),
                "kind": ft.kind_of(f["stages"])}


def apply(db, uid: str, f: dict, act: dict, lang: str) -> dict:
    """One change to the working copy: a press on the stages board, the direction, or ⬆ the latest provided stages."""
    import funnel_editor as fe
    import funnel_templates as ft

    with i18n.using(lang):
        c = _ctx(db, uid)
        f = copy.deepcopy(f)
        op = act.get("op")
        if op == "open_set":
            choices = fe.board_choices(c["configs"], uid)
            got = choices.get(act.get("set"))
            if got is None:
                return {"funnel": f, "problem": i18n.t("That Set is no longer available.")}
            return {"funnel": f, "goto": "#lattice/sets/" + (act["set"] if got.get("provided") else f"saved:{got['config']}")}
        if op == "direction":
            f["direction"] = "short" if act.get("direction") == "short" else "long"
            fe.follow_all(f, c["library"])
            return {"funnel": f, "problem": None}
        if op == "latest":
            latest = fe.template(f.get("market") or "crypto", f["direction"], ft.kind_of(f["stages"]))
            f["stages"] = copy.deepcopy(latest["stages"])
            return {"funnel": f, "problem": None}
        choices = fe.board_choices(c["configs"], uid)
        problem = fe.apply_action(f, act, choices, c["library"], c["saved_sets"])
        return {"funnel": f, "problem": problem}


def provided(db, uid: str, kind: str, market: str, direction: str, lang: str) -> dict:
    """A provided funnel, read-only, with whether you already have an unchanged copy and may make one."""
    import funnel_editor as fe
    import funnel_templates as ft
    import funnel_view as fv
    from service.lattice import _plan

    with i18n.using(lang):
        kind = kind if kind in fe.KINDS else "trend"
        market = "equity" if market == "equity" else "crypto"
        direction = "short" if direction == "short" else "long"
        f = fe.template(market, direction, kind)
        board = fe.board_data(f, {}, {}, {}, False, f"new:{kind}:{market}:{direction}", readonly=True)
        funnels = fv.load_funnels(db, uid)
        import prism

        library = prism.demo_sets()
        mine = [x["name"] for x in funnels if x.get("market") == market and x.get("direction") == direction
                and ft.kind_of(x["stages"]) == kind and fe.provenance(x, library) == i18n.t("Your copy of a provided funnel")]
        plan, display, _ = _plan(db, uid)
        return {"funnel": f, "board": board, "about": i18n.t(fe.ABOUT[kind]) if kind in fe.ABOUT else "",
                "copy": mine[0] if mine else None, "limit": _limit(plan), "count": len(funnels), "display": display,
                "leave": i18n.t('{a_coin_if_market_crypto_} leaves a stage after two No closes in a row. Alerts on new Candidates.',
                                a_coin_if_market_crypto_='A coin' if market == 'crypto' else 'An equity')}


def save(db, uid: str, f: dict, lang: str) -> dict:
    """Save and activate (or create): funnel_save, then start its first check."""
    import funnel_editor as fe
    import funnel_spec as fs

    with i18n.using(lang):
        blocks, _ = fs.validate(f)
        if blocks:
            return {"status": "error", "message": blocks[0]}
        try:
            res = db.rpc("funnel_save", fe.save_args(f)).execute()
        except Exception as exc:
            text = str(exc)
            if "too_many_funnels" in text:
                return {"status": "error", "message": i18n.t("You already have 6 funnels: delete one first.")}
            return {"status": "error", "message": i18n.t('Could not save it: {text_200}', text_200=text[:200])}
        new_id = getattr(res, "data", None)
        fid = new_id if isinstance(new_id, str) else f.get("id")
        try:
            message = fe.checking_now(fid, i18n.t("Saved."), bool(f.get("paused")))
        except Exception:
            message = i18n.t("Saved.")
        return {"status": "ok", "id": fid, "message": message}


def delete(db, uid: str, fid: str, lang: str) -> dict:
    with i18n.using(lang):
        try:
            db.rpc("funnel_delete", {"p_id": fid}).execute()
            return {"status": "ok", "message": i18n.t("Funnel deleted.")}
        except Exception as exc:
            return {"status": "error", "message": i18n.t("That didn't work: {str_exc_160}", str_exc_160=str(exc)[:160])}

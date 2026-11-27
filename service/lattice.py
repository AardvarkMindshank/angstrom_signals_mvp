"""🧩 Lattice for the new app: the Signal Group and Signal Set editors' Python side (lattice_view.py, lattice_set_view.py,
lattice_editor.py, lattice_sets.py), without Streamlit. The browser runs the classic editor components unchanged
(web/src/generated/); each edit comes here to be cleaned, checked and described, exactly as in the classic app, and
saving goes through the same database functions (analysis_create_config, analysis_save_version).
"""
from __future__ import annotations

import i18n

START_NEW = "new"


def _plan(db, uid: str) -> tuple[str, str]:
    import plans

    try:
        rows = db.table("user_plans").select("plan").eq("user_id", uid).limit(1).execute().data or []
        plan = plans.normalise(rows[0].get("plan") if rows else None)
    except Exception:
        plan = plans.normalise(None)
    try:
        rows = db.table("user_preferences").select("settings").eq("user_id", uid).limit(1).execute().data or []
        settings = (rows[0] or {}).get("settings") or {} if rows else {}
    except Exception:
        settings = {}
    return plan, ("grey" if settings.get("plan_display") == "grey" else "hide"), settings


def _saved(db) -> list[dict]:
    import signal_groups_inspector as gi

    saved, _ = gi.saved_configs(db)
    return saved or []


def _source(c: dict | None) -> dict | None:
    if not c:
        return None
    return {"id": c["id"], "name": c["name"], "owner_id": c.get("owner_id"), "current_version": c.get("current_version"),
            "version": (c.get("versions") or [{}])[-1].get("version")}


# ------------------------------------------------------------------------------------------------------------- Groups

def group_static(db, uid: str, lang: str) -> dict:
    import lattice_editor as le
    import signal_families

    plan, display, _ = _plan(db, uid)
    with i18n.using(lang):
        cat = le.catalogue()
        return {"catalogue": cat, "families": signal_families.build(cat, plan, display),
                "role_hints": {k: i18n.t(v) for k, v in le.ROLE_HINT.items()}, "suggested_labels": le.SUGGESTED_LABELS}


def group_sources(db, uid: str, lang: str) -> dict:
    """"Start from": a new Group, the provided Groups (opened as your copy), and your own Groups."""
    import lattice_view as lv

    _, _, settings = _plan(db, uid)
    with i18n.using(lang):
        labels, _docs = lv._sources(_saved(db), uid, None, settings.get("show_provided", True) is not False)
        labels[START_NEW] = i18n.t("➕ New Group")
        return {"sources": [[k, v] for k, v in labels.items()]}


def group_open(db, uid: str, start: str, lang: str) -> dict:
    import lattice_editor as le
    import lattice_view as lv

    with i18n.using(lang):
        if start == START_NEW:
            return {"model": le.empty_model(), "source": None}
        _labels, docs = lv._sources(_saved(db), uid, start, True)
        if start not in docs:
            return {"model": le.empty_model(), "source": None, "warning": i18n.t("That Group can't be opened any more.")}
        doc, cfg = docs[start]
        model, why = le.from_document(doc)
        if model is None:
            return {"model": le.empty_model(), "source": None,
                    "warning": i18n.t("{why} Starting a new Group instead; the raw inspector (Groups & Sets tab) can still open it.", why=why)}
        model["name"] = f"{model['name']} (my copy)" if cfg is None else cfg["name"]
        return {"model": model, "source": _source(cfg)}


def group_screen(model_raw, lang: str) -> dict:
    import lattice_editor as le

    with i18n.using(lang):
        model = le.clean_model(model_raw)
        return le.state_for_screen(model)


def _name_taken(saved, uid, kind, name) -> bool:
    import lattice_view as lv

    return lv.name_taken(saved, uid, kind, name)


def save(db, uid: str, kind: str, doc: dict, source_id: str | None, expected: int | None, lang: str) -> dict:
    """A new Group or Set (version 1), or the next version of one you have open."""
    import lattice_view as lv
    import signal_groups_inspector as gi

    with i18n.using(lang):
        saved = _saved(db)
        word = "Group" if kind == "group" else "Set"
        try:
            if not source_id:
                if _name_taken(saved, uid, kind, doc.get("name")):
                    src = next((c for c in saved if c.get("owner_id") == uid and c.get("kind") == kind
                                and " ".join(str(c.get("name") or "").split()).casefold() == " ".join(str(doc.get("name") or "").split()).casefold()), None)
                    return {"ok": False, "message": lv.taken_message(word, doc.get("name") or "", _source(src) and {**_source(src), "current_version": src.get("current_version")})}
                new_id = db.rpc("analysis_create_config", {"kind": kind, "body": doc}).execute().data
                return {"ok": True, "id": new_id, "version": 1,
                        "message": i18n.t("Saved as a new Group (version 1). It is private until you publish it.") if kind == "group"
                        else i18n.t("Saved as a new Set (version 1). It is private until you publish it.")}
            v = db.rpc("analysis_save_version", {"cfg": source_id, "expected_version": expected, "body": doc}).execute().data
            return {"ok": True, "id": source_id, "version": v, "message": i18n.t("Saved version {v}.", v=v)}
        except Exception as exc:
            return {"ok": False, "message": i18n.t("Refused: {gi_rpc_error_exc}", gi_rpc_error_exc=gi._rpc_error(exc))}


def group_save(db, uid: str, model_raw, source_id, expected, lang: str) -> dict:
    import lattice_editor as le

    with i18n.using(lang):
        model = le.clean_model(model_raw)
        screen = le.state_for_screen(model)
        if not screen["can_save"]:
            return {"ok": False, "message": i18n.t("⛔ Can't save: {b}", b="; ".join(screen["checks"]["blocks"]))}
    return save(db, uid, "group", le.to_document(model), source_id, expected, lang)


def group_try(db, model_raw, kind: str, aid: str, lang: str) -> dict:
    import lattice_editor as le
    import signal_groups as sg
    import signal_library as sl
    from signal_library import loaders

    with i18n.using(lang):
        model = le.clean_model(model_raw)
        ctx = sl.DataContext(kind, aid, sentiment_loader=loaders.sentiment_loader(db), options_loader=loaders.options_loader(db))
        result = sg.evaluate_group(le.to_document(model), ctx)
        score = (result.get("score") or {}).get("value")
        outcome = result.get("outcome") or {}
        return {"score": None if score is None else round(score * 100), "label": outcome.get("label"),
                "qualified": bool(outcome.get("qualified")), "status": result.get("status")}


def delete_check(db, uid: str, kind: str, cfg_id: str, lang: str) -> dict:
    """Whether a Group or Set can be deleted: refused while a Set (or a Prism scan) is built on it."""
    import lattice_delete as ld

    with i18n.using(lang):
        if kind == "group":
            users = ld.sets_using(cfg_id, _saved(db), uid)
        else:
            try:
                scans = db.table("prism_scans").select("name, set_source").execute().data or []
            except Exception:
                scans = []
            users = ld.scans_using(cfg_id, scans)
        return {"ok": not users, "message": ld.blocked_message(kind, users) if users else ""}


# --------------------------------------------------------------------------------------------------------------- Sets

def _set_context(db, uid: str):
    import lattice_sets as ls

    saved = _saved(db)
    return saved, ls.group_choices(saved, uid)


def set_sources(db, uid: str, lang: str) -> dict:
    import lattice_set_view as lsv

    _, _, settings = _plan(db, uid)
    with i18n.using(lang):
        saved, choices = _set_context(db, uid)
        starts = [[START_NEW, i18n.t("➕ New Set")]]
        if settings.get("show_provided", True) is not False:
            starts += [[k, label] for k, (label, _) in lsv._provided_starts(choices).items()]
        starts += [[f"saved:{c['id']}", f"🗂️ {c['name']} (yours, v{c['versions'][-1]['version']})"]
                   for c in saved if c.get("kind") == "set" and c.get("owner_id") == uid and c.get("versions")]
        return {"sources": starts}


def set_open(db, uid: str, start: str, lang: str) -> dict:
    import lattice_set_view as lsv
    import lattice_sets as ls

    with i18n.using(lang):
        saved, choices = _set_context(db, uid)
        if start == START_NEW:
            return {"model": ls.empty_model(), "source": None}
        provided = lsv._provided_starts(choices)
        if start in provided:
            model = provided[start][1]
            model["name"] = f"{model.get('name') or 'Set'} (my copy)"
            return {"model": model, "source": None}
        cfg = next((c for c in saved if f"saved:{c['id']}" == start and c.get("owner_id") == uid and c.get("versions")), None)
        if not cfg:
            return {"model": ls.empty_model(), "source": None, "warning": i18n.t("That Set can't be opened any more.")}
        model, why = ls.from_document(cfg["versions"][-1]["body"], choices)
        if model is None:
            return {"model": ls.empty_model(), "source": None, "warning": i18n.t("{why} Starting a new Set instead.", why=why)}
        model["name"] = cfg["name"]
        return {"model": model, "source": _source(cfg)}


def set_screen(db, uid: str, model_raw, lang: str) -> dict:
    import lattice_sets as ls

    with i18n.using(lang):
        _, choices = _set_context(db, uid)
        model = ls.clean_model(model_raw or ls.empty_model(), choices)
        return ls.state_for_screen(model, choices)


def set_save(db, uid: str, model_raw, source_id, expected, lang: str) -> dict:
    import lattice_sets as ls

    with i18n.using(lang):
        _, choices = _set_context(db, uid)
        model = ls.clean_model(model_raw or ls.empty_model(), choices)
        screen = ls.state_for_screen(model, choices)
        if not screen["can_save"]:
            return {"ok": False, "message": i18n.t("⛔ Can't save: {b}", b="; ".join(screen["checks"]["blocks"]))}
        doc = ls.to_document(model, choices)
    out = save(db, uid, "set", doc, source_id, expected, lang)
    if out.get("ok") and not source_id:
        with i18n.using(lang):
            out["message"] = i18n.t("Saved as a new Set (version 1).") + (i18n.t(" It now appears in 🔎 Prism.") if screen.get("scannable") else "")
    return out


def set_search(raw: str) -> dict | None:
    import lattice_set_view as lsv

    return lsv.fixed_asset_matches(raw)


def study(db, uid: str, cfg_id: str, ask: bool, lang: str) -> dict:
    """🔬 What followed for one of your saved Sets: the finished study, where its study is, or (ask) queue it."""
    import perspectives
    import what_followed as wf

    with i18n.using(lang):
        cfg = next((c for c in _saved(db) if c["id"] == cfg_id and c.get("owner_id") == uid and c.get("versions")), None)
        if not cfg:
            return {"state": "none"}
        version = cfg["versions"][-1]
        doc = version["body"]
        try:
            perspectives.load_studies(db, force=ask)
        except Exception:
            pass
        card = perspectives.followed_card(doc)
        if card:
            icon, _ = perspectives.evidence(doc)
            return {"state": "done", "icon": icon, "card": card}
        ok, why = wf.studyable(doc)
        if not ok:
            return {"state": "no", "why": why}
        h = wf.logic_hash(doc)
        if ask:
            try:
                got = db.rpc("request_set_study", {"set_hash": h, "body": doc, "name": cfg.get("name") or ""}).execute().data
                if got == "queued":
                    try:
                        import study_nudge

                        study_nudge.nudge()
                    except Exception:
                        pass
                return {"state": got or "queued", "version": version["version"]}
            except Exception as exc:
                import signal_groups_inspector as gi

                msg = gi._rpc_error(exc)
                return {"state": "error", "why": i18n.t("You already have 5 studies waiting; try again when one finishes.")
                        if "too_many_waiting" in msg else i18n.t("Could not queue the study: {msg}", msg=msg)}
        try:
            row = (db.table("set_studies").select("status, error, requested_at").eq("set_hash", h).limit(1).execute().data or [None])[0]
        except Exception:
            row = None
        return {"state": (row or {}).get("status") or "none", "error": (row or {}).get("error"), "version": version["version"]}

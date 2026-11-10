"""
Saved Groups and Sets for the training-video demo page, built with the app's own editor code, so they are exactly
what a person would have saved in the earlier videos:

* the starter Groups, as the database holds them (no labels);
* "My Trend" (video 3): moving averages, Ichimoku cloud and MACD line scored together, Bullish at +30 or more,
  Bearish at -30 or less, otherwise Neutral, with a veto when the daily regime is ranging;
* "Pullback in an uptrend" (video 4): My Trend is Bullish, and Stochastic %K is at most 30 (the close near the
  bottom of its recent range).
"""

from __future__ import annotations

import lattice_editor as le
import lattice_sets as ls
import signal_groups as sg

USER = "demo"
MY_TREND, PULLBACK = "cfg-my-trend", "cfg-pullback"


def _version(cfg_id: str, version: int, body: dict) -> dict:
    return {"config_id": cfg_id, "version": version, "body": body, "capture_ceiling": None,
            "created_at": f"2026-11-0{version}T00:00:00Z", "change_note": ""}


def config(cfg_id: str, kind: str, body: dict, owner: str = USER, starter: str | None = None) -> dict:
    return {"id": cfg_id, "kind": kind, "name": body["name"], "owner_id": owner, "starter_alias": starter,
            "current_version": 1, "archived": False, "copied_from_config": None,
            "versions": [_version(cfg_id, 1, body)]}


def my_trend_model() -> dict:
    cat = {s["id"]: s for s in le.catalogue()}
    model = le.empty_model()
    model["name"] = "My Trend"
    for sid in ("ma.position", "ichimoku.position", "macd.level", "regime.observation"):
        model["members"].append({"key": le.new_member_key(model, sid, "1D"), "id": sid, "version": cat[sid]["version"],
                                 "timeframe": "1D", "role": "condition" if sid == "regime.observation" else "score"})
    model["rules"] = [
        {"id": "bullish", "label": "Bullish", "joiner": "all", "clauses": [{"operand": "score", "op": "gte", "value": "+30"}]},
        {"id": "bearish", "label": "Bearish", "joiner": "all", "clauses": [{"operand": "score", "op": "lte", "value": "−30"}]}]
    model["conditions"] = [{"key": "veto", "label": "Daily regime is ranging", "kind": "veto", "joiner": "all",
                            "clauses": [{"operand": "regime_observation_1d:state", "op": "is", "value": "ranging"}]}]
    return le.clean_model(model)


def starters() -> list[dict]:
    """The starter Groups, and the other provided Groups (as the live database holds them after
    sql/2026-11-15_provided_groups.sql), such as Recent structure break."""
    import prism

    out = [config(f"cfg-{a.split(':')[1]}", "group", sg.starter(a), owner="system", starter=a) for a in sg.STARTERS]
    out += [config(f"cfg-{k.split(':')[1]}", "group", body, owner="system", starter=k)
            for k, (_, body) in prism.provided_groups().items() if k not in sg.STARTERS]
    return out


def pullback_model(choices: dict) -> dict:
    model = ls.empty_model()
    model.update(name="Pullback in an uptrend", purpose="The main trend is up, but price has dipped in the short term.")
    model["groups"] = [{"key": "my_trend", "source": f"saved:{MY_TREND}:1"}]
    model["standalone"] = [{"key": "level_1d", "id": "stochastic.level", "version": 1, "timeframe": "1D",
                            "role": "condition"}]
    model["lines"] = [{"target": "outcome", "group": "my_trend", "op": "is", "value": "bullish"},
                      {"target": "member", "member": "level_1d", "field": "stoch_k", "op": "lte", "value": "30"}]
    return ls.clean_model(model, choices)


def configs(which: set[str]) -> list[dict]:
    """The saved configs for a video: starters always; "trend" adds My Trend; "pullback" adds the Set too."""
    out = starters()
    if "trend" in which or "pullback" in which:
        out.append(config(MY_TREND, "group", le.to_document(my_trend_model())))
    if "pullback" in which:
        choices = ls.group_choices(out, USER)
        out.append(config(PULLBACK, "set", ls.to_document(pullback_model(choices), choices)))
    return out


if __name__ == "__main__":                       # a quick check that everything is valid and scannable
    import json

    print("My Trend:", json.dumps(le.state_for_screen(my_trend_model())["checks"]))
    saved = configs({"pullback"})
    choices = ls.group_choices(saved, USER)
    screen = ls.state_for_screen(pullback_model(choices), choices)
    print("Pullback:", screen["checks"], "scannable:", screen["scannable"])
    print(screen["description"])
    print([t["key"] + " = " + t["label"] for t in screen["targets"]][:40])

"""
Writes the browser harness for the Lattice Group editor component (checked by lattice_component_check.js in CI).

The harness stands in for Streamlit: it gives the component the same data Python would send and records what the
component sends back, so a real browser can click, tap and drag through it.

    python lattice_component_check.py --out out/lattice
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lattice_component as lc
import lattice_editor as le
import prism


def harness_model() -> dict:
    model, _ = le.from_document(prism.labelled_starter("starter:trend"))
    model["members"].append({"key": "rsi_level_1d", "id": "rsi.level", "version": 1, "timeframe": "1D",
                             "role": "condition"})
    model["rules"][0]["clauses"].append({"operand": "rsi_level_1d:rsi", "op": "lte", "value": "70"})
    return model


def page(model: dict) -> str:
    data = {**le.state_for_screen(model), "catalogue": le.catalogue(), "role_hints": le.ROLE_HINT,
            "suggested_labels": le.SUGGESTED_LABELS}
    script = lc.JS.replace("export default function(component)", "window.renderLattice = function(component)")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Lattice editor check</title>
<style>{lc.CSS} body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}}</style></head>
<body><div id="host"></div><script>
{script}
window.sent = [];
window.baseData = {json.dumps(data)};
window.draw = (model) => window.renderLattice({{data: Object.assign({{}}, window.baseData, model ? {{model}} : {{}}),
  parentElement: document.getElementById("host"),
  // like Streamlit: each edit comes back and the component is drawn again with the edited model
  setTriggerValue: (k, v) => {{ const m = JSON.parse(v); window.sent.push([k, m]); setTimeout(() => window.draw(m), 0); }}}});
window.draw(null);
window.ready = true;
</script></body></html>"""


def harness_set() -> tuple[dict, dict]:
    import signal_groups as sg

    import lattice_sets as ls

    saved = [{"id": "11111111-1111-1111-1111-111111111111", "kind": "group", "name": "Trend (with labels)",
              "owner_id": "me", "starter_alias": None, "current_version": 1,
              "versions": [{"version": 1, "body": prism.labelled_starter("starter:trend")}]},
             {"id": "22222222-2222-2222-2222-222222222222", "kind": "group", "name": "Flow", "owner_id": None,
              "starter_alias": "starter:flow", "current_version": 1,
              "versions": [{"version": 1, "body": sg.starter("starter:flow")}]}]
    choices = ls.group_choices(saved, "me")
    model = ls.clean_model({"name": "Daily check", "groups": [{"source": next(iter(choices))}],
                            "lines": [{"target": "outcome", "group": "trend_with_labels", "op": "is",
                                       "value": "bullish"}]}, choices)
    return model, choices


def set_page(model: dict, choices: dict) -> str:
    import lattice_sets as ls

    data = {**ls.state_for_screen(model, choices), "catalogue": le.catalogue()}
    script = lc.SET_JS.replace("export default function(component)", "window.renderLattice = function(component)")
    return page_shell(script, data, "Lattice Set editor check")


def page_shell(script: str, data: dict, title: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{lc.CSS} body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}}</style></head>
<body><div id="host"></div><script>
{script}
window.sent = [];
window.baseData = {json.dumps(data)};
window.draw = (model) => window.renderLattice({{data: Object.assign({{}}, window.baseData, model ? {{model}} : {{}}),
  parentElement: document.getElementById("host"),
  // like Streamlit: each edit comes back and the component is drawn again with the edited model
  setTriggerValue: (k, v) => {{ const m = JSON.parse(v); window.sent.push([k, m]); setTimeout(() => window.draw(m), 0); }}}});
window.draw(null);
window.ready = true;
</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/lattice")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "editor.html").write_text(page(harness_model()), encoding="utf-8")
    (out / "set_editor.html").write_text(set_page(*harness_set()), encoding="utf-8")
    print(f"wrote {out / 'editor.html'}")


if __name__ == "__main__":
    main()

"""
Writes the browser harness for the funnel stages board (checked by funnel_stages_check.js in CI).

The harness stands in for Streamlit: it gives the board the data the editor would send (a provided long funnel with
one stage on an older Set version, and one Set of your own) and records each action the board sends back.

    python funnel_stages_check.py --out out/funnel_stages
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import funnel_editor as fe
import funnel_stages_component as fc
import prism


def board_data() -> dict:
    lib = prism.demo_sets()
    saved = [{"id": "cfg1", "kind": "set", "name": "My daily trend", "owner_id": "me",
              "versions": [{"version": 1, "body": lib["demo:ema_up_1d"]}]}]
    f = fe.template("crypto", "long")
    f["stages"][1]["set_body"]["decision"]["rule"]["eq"] = "fast_below"        # an older version: ⬆ shows
    return fe.board_data(f, fe.board_choices(saved, "me"), lib, {}, True, "f1")


def page(data: dict, night: bool = False) -> str:
    script = fc.JS.replace("export default function funnelStages(component)",
                           "window.funnelStages = function funnelStages(component)")
    return f"""<!doctype html><html lang="en"{' class="angstrom-night"' if night else ""}><head><meta charset="utf-8"><title>Funnel stages check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{fc.CSS} body{{font-family:system-ui,sans-serif;margin:16px;background:{'#1e2028' if night else '#fff'};color:{'#e5e7eb' if night else '#111'}}}</style></head>
<body><div id="host"></div><script>
{script}
window.sent = [];
window.boardData = {json.dumps(data)};
window.funnelStages({{data: window.boardData, parentElement: document.getElementById("host"),
  setTriggerValue: (k, v) => window.sent.push([k, JSON.parse(v)])}});
window.ready = true;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/funnel_stages")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "board.html").write_text(page(board_data()))
    (out / "board_night.html").write_text(page(board_data(), night=True))
    print(f"wrote {out / 'board.html'}")


if __name__ == "__main__":
    main()

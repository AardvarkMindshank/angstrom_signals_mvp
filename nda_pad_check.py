"""
Writes the browser harness for the NDA signature pad (checked by nda_pad_check.js in CI).

    python nda_pad_check.py --out out/nda_pad
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nda_component as nc


def page() -> str:
    script = nc.JS.replace("export default function(component)", "window.renderPad = function(component)")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Signature pad check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{nc.CSS} body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}}</style></head>
<body><div id="host"></div><script>
{script}
window.sent = [];
window.draw = () => window.renderPad({{parentElement: document.getElementById("host"),
  setStateValue: (k, v) => window.sent.push([k, v])}});
window.draw();
window.ready = true;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/nda_pad")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pad.html").write_text(page())
    print(f"wrote {out / 'pad.html'}")


if __name__ == "__main__":
    main()

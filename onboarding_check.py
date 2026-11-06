"""
Writes the browser harness for tap-to-explain (checked by onboarding_check.js in CI): the real page-wide script
with a few sample elements, including one inside a shadow root as Streamlit components use.

    python onboarding_check.py --out out/onboarding
"""

from __future__ import annotations

import argparse
from pathlib import Path

import onboarding


def page() -> str:
    script = onboarding.TAP_JS.replace("export default function(component)", "window.tapExplain = function(component)")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Tap to explain check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{onboarding.TAP_CSS} body{{font-family:system-ui,sans-serif;margin:24px}} .gap{{margin:28px 0}}</style></head>
<body>
<p class="gap"><span id="reading" title="Trend +42: price is above its 50- and 200-day averages.">📈 +42</span></p>
<p class="gap"><button id="act" title="Run now on 12 assets">▶</button> <span id="clicks">0</span></p>
<p class="gap"><span id="rowcell" style="cursor:pointer" title="Click to open the breakdown">Bitcoin</span></p>
<p class="gap"><span id="plain">no note here</span></p>
<div id="host" class="gap"></div>
<script>
{script}
document.getElementById("act").addEventListener("click", () => {{
  const c = document.getElementById("clicks"); c.textContent = String(Number(c.textContent) + 1); }});
const root = document.getElementById("host").attachShadow({{mode: "open"}});
root.innerHTML = '<span id="inner" title="🧩 Worked out by the starter Trend Group">🧩</span>';
window.tapExplain({{data: {{on: false}}}});
window.ready = true;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/onboarding")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tap.html").write_text(page())
    print(f"wrote {out / 'tap.html'}")


if __name__ == "__main__":
    main()

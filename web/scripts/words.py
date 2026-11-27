"""The new app's words in each language: every text web/src passes to T(), looked up in the app's locales/ files (the
same translations the classic app uses), written to web/public/words/<code>.json before the build."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import i18n  # noqa: E402

sources = []
for path in sorted(glob.glob(os.path.join(ROOT, "web", "src", "**", "*.js*"), recursive=True)):
    with open(path, encoding="utf-8") as fh:
        sources.append(fh.read())
out = os.path.join(ROOT, "web", "public", "words")
os.makedirs(out, exist_ok=True)
for lang in i18n.LANGUAGES:
    if lang["code"] == i18n.BASE:
        continue
    with open(os.path.join(out, f"{lang['code']}.json"), "w", encoding="utf-8") as fh:
        json.dump(i18n.js_words(*sources, code=lang["code"]), fh, ensure_ascii=False)
print(f"words for {len(i18n.LANGUAGES) - 1} languages")

# The macro calendar (macro_calendar.py, the same dates Tides uses), for the asset page's "Events ahead".
import macro_calendar  # noqa: E402

data = os.path.join(ROOT, "web", "public", "data")
os.makedirs(data, exist_ok=True)
with open(os.path.join(data, "calendar.json"), "w", encoding="utf-8") as fh:
    json.dump([{"kind": e["kind"], "at": e["at"].isoformat(), "tier": e["tier"], "reference": e["reference"]}
               for e in macro_calendar.events()], fh)
print("calendar written")

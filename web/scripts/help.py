"""📖 Help and guides for the new app, in every language: web/public/help/<code>.json, written before each build.

The topic texts are the classic app's own (its _render_help_guides in app.py, read without running it), with their
translations, so the two apps explain things in the same words. "Start here" is written for the new app (below).
Each file is {"topics": [{"key", "title", "icon", "blocks": [markdown…]}], "videos": [series…]}.
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import i18n  # noqa: E402
from i18n import mark  # noqa: E402

START = [mark("""**MarketNavi reads current market conditions for the crypto and equities you follow.** Each asset gets three
technical readings (Trend, Stretch and Flow), a news sentiment score, and tools to look closer. It is a research
tool, not financial advice: the readings describe conditions now, and none has been shown to predict which way
price goes next.

**One scale for every score.** All of them run from **-100 to +100**: 0 is neutral or mixed, above 0 is up or
positive, below 0 is down or negative, and the further from 0, the stronger. They measure different things, so
they are never added together.

**Finding your way**
- **Quick Snapshot** is where the day starts: the daily video, the Morning Outlook and your Passage Plan, the
  Tides card, what changed since your last visit, your funnels and the main markets.
- **Signals** lists your watchlist (or a funnel's assets) with the readings you choose; click a name to open it.
- An **asset page** has the chart (Simple, Technical or Pro, with every indicator and the drawing tools), the
  readings, your Sets, the news, derivatives, conditions, your own activity and the community's comments.
- **Tides** is the macro picture; **Lattice** is your research workspace (Signal Groups, Signal Sets, Prism Scan
  and Funnels); the **Logbook** keeps each day's video, Outlook and plan for two weeks; the **Trade Log** reviews
  your own trades.
- Search (Ctrl K) finds any asset, page or topic. **Social** and the **Navigator** open on the right; pin the panel
  to keep it beside the page on a wide screen. The bell shows your alerts; the gear opens Settings.
"""), mark("""**Your settings** are saved on your account and follow you to any device: language, day or night, your
watchlists, alerts and emails, the AI you prefer, and who can message you. Hover an icon or a reading for what
it means.""")]

TABS = [  # (key, the classic tab's variable, title, icon)
    ("start", "tab_start", mark("🚀 Start here"), "rocket"),         # the classic tab names (the page drops the emoji)
    ("signals", "tab_scores", mark("📈 Signals"), "trending-up"),
    ("chart", "tab_chart", mark("📊 Chart & tools"), "chart-column"),
    ("sentiment", "tab_sentiment", mark("📰 Sentiment"), "newspaper"),
    ("tides", "tab_tides", "🌊 Tides", "waves-horizontal"),
    ("lattice", "tab_lattice", mark("🧩 Lattice & Prism"), "puzzle"),
    ("funnels", "tab_funnels", mark("🔻 Funnels"), "funnel"),
    ("alerts", "tab_alerts", mark("🔔 Alerts"), "bell"),
    ("social", "tab_social", mark("💬 Social"), "message-circle"),
]


# Paragraphs of the classic texts that describe the classic layout, replaced for the new app (topic, block, paragraph):
# the rest of each block stays the classic app's own words and translations.
NEW_APP = {
    ("lattice", 0, 0): mark("""**Lattice** is the research workspace, a page of its own in the bar at the top. Pick a part from its tabs:
Signal Groups, Signal Sets, Prism Scan, Funnels and Soundings; hover a tab for what it does. Anything it draws on a
chart (such as Visualize History) shows right there in Lattice. Like the rest of the app, it describes conditions;
nothing in it is a forecast or advice."""),
    ("sentiment", 0, 2): mark("""**Where it shows**
- **Market sentiment – Crypto / Stocks** (from the Quick Snapshot or Search): the whole market, from headlines plus
  public readings (central banks, the dollar and yields, Fear & Greed, market breadth and more).
- The **News** tab of each asset's page: the headlines for that asset, newest first, each with its score and a
  one-line summary, plus Positive and Negative paragraphs.
- The **Sentiment** column in the tables."""),
}


def new_app(code: str, key: str, blocks: list) -> list:
    """The classic blocks with NEW_APP's paragraphs swapped in (only when the paragraphs line up as expected)."""
    out = list(blocks)
    with i18n.using(code):
        for (k, b, para), text in NEW_APP.items():
            if k != key or b >= len(out):
                continue
            parts = out[b].strip().split("\n\n")
            if para < len(parts):
                parts[para] = i18n.t(text)
                out[b] = "\n\n".join(parts)
    return out


def classic_blocks() -> dict:
    """{tab variable: [(text, kwargs-name or None)]}: the t("…") texts each classic help tab shows, in order."""
    tree = ast.parse(open(os.path.join(ROOT, "app.py"), encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_render_help_guides")
    out = {}
    for w in [n for n in fn.body if isinstance(n, ast.With)]:
        tab = w.items[0].context_expr.id
        blocks = []
        for n in ast.walk(w):
            if not (isinstance(n, ast.Call) and getattr(n.func, "attr", None) in ("markdown", "caption") and n.args):
                continue
            a = n.args[0]
            if isinstance(a, ast.Call) and getattr(a.func, "id", None) == "t" and a.args:
                x = a.args[0]
                if isinstance(x, ast.Constant) and isinstance(x.value, str):
                    blocks.append((x.value, a.keywords[0].arg if a.keywords else None))
                elif isinstance(x, ast.Attribute) and x.attr == "EXPLAINER":
                    blocks.append(("@EXPLAINER", None))
            elif isinstance(a, ast.Name) and a.id == "SENTIMENT_METHOD":
                blocks.append(("@SENTIMENT_METHOD", None))
            elif isinstance(a, ast.BinOp) and "Current | Family" in ast.unparse(a):
                blocks.append(("@CURRENTS", None))
        out[tab] = blocks
    return out


def _sentiment_method() -> str:
    tree = ast.parse(open(os.path.join(ROOT, "app.py"), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "SENTIMENT_METHOD":
            # An f-string of fixed numbers, evaluated with the few names it uses (it is English in both apps).
            import news_filter
            import sentiment

            names = {"news_filter": news_filter, "MACRO_MOODS": sentiment.MACRO_MOODS,
                     "MIN_SCORED_SHARE": getattr(sentiment, "MIN_SCORED_SHARE", None), "int": int}
            return eval(compile(ast.Expression(n.value), "app.py", "eval"), names)   # noqa: S307
    return ""


def topics(code: str, blocks: dict) -> list:
    import signals_view
    import tides as td

    out = []
    with i18n.using(code):
        t = i18n.t
        for key, var, title, icon in TABS:
            if key == "start":
                texts = [t(x) for x in START]
            else:
                texts = []
                for text, kw in blocks.get(var, []):
                    if text == "@EXPLAINER":
                        texts.append(t(signals_view.EXPLAINER))
                    elif text == "@SENTIMENT_METHOD":
                        try:
                            texts.append(_sentiment_method())
                        except Exception:
                            pass
                    elif text == "@CURRENTS":
                        texts.append(t("| Current | Family | What it measures | Votes in the Tide |") + "\n|---|---|---|---|\n" + "\n".join(
                            f"| {c['icon']} **{t(c['name'])}** | {td.FAMILIES[c['family']][2]} {t(td.FAMILIES[c['family']][0])} "
                            f"| {t(c['measures']).replace('|', '/')} | {t('✅ yes') if c['weight'] else t('shown only')} |"
                            for c in td.SPEC.values()))
                    elif kw == "fam":
                        fam = ", ".join(f"{t(name)} {weight:.0%}" for name, weight, _icon in td.FAMILIES.values())
                        texts.append(t(text, fam=fam))
                    elif kw is None:
                        texts.append(t(text))
            out.append({"key": key, "title": t(title), "icon": icon, "blocks": new_app(code, key, texts)})
    return out


def videos() -> list:
    import training_videos as tv

    return [{"key": k, "name": name, "videos": [{"slug": s, "title": title, "length": length, "url": tv.BASE_URL + s + ".mp4"}
                                                for s, title, length in vids]} for k, (name, vids) in tv.SERIES.items()]


def main() -> None:
    out_dir = os.path.join(ROOT, "web", "public", "help")
    os.makedirs(out_dir, exist_ok=True)
    blocks = classic_blocks()
    vids = videos()
    codes = ["en"] + [x["code"] for x in i18n.LANGUAGES if x.get("status") == "live" and x["code"] != "en"]
    for code in codes:
        with open(os.path.join(out_dir, f"{code}.json"), "w", encoding="utf-8") as fh:
            json.dump({"topics": topics(code, blocks), "videos": vids}, fh, ensure_ascii=False)
    print("help written for", len(codes), "languages")


if __name__ == "__main__":
    main()

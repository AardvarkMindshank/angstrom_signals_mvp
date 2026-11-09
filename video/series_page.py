"""The training videos page: angstromsignals.com/videos/training/ (index.html in that folder).

Not linked from the website's menus, and asks search engines not to list it: it is for beta testers, who get the
address directly. Built from training_videos.SERIES (order, titles, lengths) and video/publish.txt (the recording
each published video came from, whose date is shown as the upload date). Regenerated and uploaded by the
video-publish workflow.

    python video/series_page.py out/page
"""

from __future__ import annotations

import html
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import training_videos as tv  # noqa: E402

DESCRIPTIONS = {
    "01-angstrom-lattice-at-a-glance": "The research workspace in a minute and a half: Signals, Groups, Sets and "
                                       "Prism Scan, and how they fit together.",
    "02-signals": "Single measurements of the market from price and volume, each answering one question.",
    "03-signal-groups": "Turn several signals into one reading: a score from −100 to +100 and a label such as "
                        "Bullish.",
    "04-signal-sets": "Turn readings into a decision, Yes, No or Unknown, with the reason shown.",
    "05-prism-scan": "Check your whole watchlist with your own Sets, on a schedule, with alerts.",
    "w1-trend-with-volume": "A rising trend that volume backs up, built and scanned from start to finish.",
    "w2-overextended-rally": "A caution flag rather than an entry: a strong trend that has run very hot.",
    "w3-breakout-with-volume": "A breakout from rising structure, with a crowd turning up for it.",
    "06-provided-library": "The Groups and Sets that come with Angstrom Signals, built around common trading "
                           "situations.",
    "07-visualize-history": "What a Set said on every past day, as coloured bands behind the price.",
    "08-what-followed": "When a Set turns Yes, does anything different tend to happen next? How the study works "
                        "and what its verdicts mean.",
}


def published() -> dict[str, date]:
    """Video name -> the date of the recording it was published from."""
    out = {}
    for line in (ROOT / "video" / "publish.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "/" not in line:
            continue
        folder, slug = line.rsplit("/", 1)
        try:
            out[slug] = date.fromisoformat(folder[:10])
        except ValueError:
            out[slug] = date.today()
    return out


def page() -> str:
    dates = published()
    sections = []
    for _, (series, videos) in tv.SERIES.items():
        rows = []
        for n, (slug, title, length) in enumerate(videos, 1):
            if slug not in dates:
                continue
            when = dates[slug]
            rows.append(
                "<tr>"
                f"<td class='n'>{n}</td>"
                f"<td><a href='{html.escape(slug)}.mp4'>{html.escape(title)}</a>"
                f"<div class='d'>{html.escape(DESCRIPTIONS.get(slug, ''))}</div></td>"
                f"<td class='len'>{html.escape(length)}</td>"
                f"<td class='when'><time datetime='{when.isoformat()}'>{when.day} {when:%b %Y}</time></td>"
                "</tr>")
        if rows:
            sections.append(f"<h2>{html.escape(series)}</h2><table><thead><tr><th>#</th><th>Video</th>"
                            "<th>Length</th><th>Uploaded</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Training videos · Angstrom Signals</title>
<style>
:root{{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#1e3a8a;--bg:#ffffff;--soft:#f8fafc}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e2e8f0;--muted:#94a3b8;--line:#1e293b;--accent:#93c5fd;--bg:#0b1220;--soft:#111a2e}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:880px;margin:0 auto;padding:40px 16px 64px}}
header{{display:flex;align-items:center;gap:14px;margin-bottom:8px}}
header img{{height:44px;width:auto}}
.brand{{font-size:1.5rem;font-weight:700;letter-spacing:-.01em}}
.lead{{color:var(--muted);margin:0 0 28px}}
h2{{font-size:1.1rem;margin:32px 0 8px}}
table{{width:100%;border-collapse:collapse;table-layout:fixed}}
th:nth-child(1){{width:2.5rem}}th:nth-child(3){{width:5rem}}th:nth-child(4){{width:7.5rem}}
th{{text-align:left;font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
   font-weight:600;padding:8px 10px;border-bottom:2px solid var(--line)}}
td{{padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:hover td{{background:var(--soft)}}
td.n{{width:2.5rem;color:var(--muted);font-variant-numeric:tabular-nums}}
td.len,td.when{{white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums}}
a{{color:var(--accent);font-weight:600;text-decoration:none}}
a:hover{{text-decoration:underline}}
.d{{color:var(--muted);font-size:.92rem;margin-top:2px}}
footer{{margin-top:40px;color:var(--muted);font-size:.85rem}}
@media (max-width:560px){{th:nth-child(3),td.len{{display:none}}th:nth-child(4){{width:6.5rem}}}}
</style></head>
<body><main>
<header><picture><source srcset="logo-dark.png" media="(prefers-color-scheme: dark)"><img src="logo.png" alt="">
</picture><span class="brand">angstrom signals</span></header>
<p class="lead">Training videos for the Angstrom Lattice research workspace. Each opens in your browser; captions are
part of the picture.</p>
{''.join(sections)}
<footer>Descriptive readings, not forecasts or advice. For beta testers: please don't share this page.</footer>
</main></body></html>
"""


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(), encoding="utf-8")
    shutil.copy(ROOT / "assets" / "logo-light.png", out / "logo.png")
    shutil.copy(ROOT / "assets" / "logo-dark.png", out / "logo-dark.png")
    print(f"wrote {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "out/page")))

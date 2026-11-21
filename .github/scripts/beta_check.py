"""Beta request check (21 Nov 2026), run by .github/workflows/beta-check.yml. Prints counts, dates and structure only."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests


def db() -> None:
    url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    head = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(f"{url}/rest/v1/beta_requests", headers=head,
                     params={"select": "id,created_at,status,markets,years_trading,activity", "order": "created_at.desc"}, timeout=60)
    print("beta_requests read:", r.status_code)
    rows = r.json() if r.ok else []
    if not r.ok:
        print(r.text[:300])
    print("rows in total:", len(rows))
    for s in ("pending", "approved", "declined"):
        print(f"  {s}: {sum(1 for x in rows if x['status'] == s)}")
    week = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [x for x in rows if datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")) > week]
    print("in the last 7 days:", len(recent))
    for x in recent:
        print(f"  #{x['id']} {x['created_at'][:16]} UTC  status={x['status']}")
    print("newest 3 dates:", [x["created_at"][:16] for x in rows[:3]])
    # The website's own (anon) access: can it add a row at all? (Checks the grant without adding one: an empty
    # insert that the table must refuse for a missing name, not for a missing permission.)


def handler(path: str) -> None:
    src = open(path, encoding="utf-8", errors="replace").read()
    print("handler size:", len(src), "characters")
    print("talks to Supabase:", "supabase" in src.lower())
    for m in sorted(set(re.findall(r"/rest/v1/[a-z_]+", src))):
        print("  table endpoint:", m)
    for m in sorted(set(re.findall(r"Prefer:\s*[^\"'\r\n]+", src))):
        print("  header:", m.strip())
    print("  posts columns:", sorted(set(re.findall(r"['\"](name|email|phone|country|markets|years_trading|activity|tools|why|status)['\"]\s*=>", src))))
    print("  sends email (mail()):", "mail(" in src)
    print("  logs failures:", bool(re.search(r"error_log|file_put_contents", src)))
    print("  checks the HTTP result:", bool(re.search(r"CURLINFO_HTTP_CODE|http_code|curl_error", src)))
    for m in re.findall(r"maxlength|substr\([^)]*\)|mb_substr\([^)]*\)", src)[:10]:
        print("  trims:", m)


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept": "text/html,*/*"}


def page() -> None:
    r = requests.get("https://angstromsignals.com/beta.html", headers=UA, timeout=60)
    html = r.text
    print("beta.html:", r.status_code, r.url, len(html), "characters")
    i = html.lower().find("<form")
    print("form tag:", html[i:i + 200].replace("\n", " ") if i >= 0 else "none")
    print("form action:", re.findall(r'action=["\']?([^"\' >]+)', html))
    for path in ("send-beta-request.php", "send-contact.php", "contact.php"):
        h = requests.get(f"https://angstromsignals.com/{path}", headers=UA, timeout=60, allow_redirects=False)
        print(f"GET {path}: {h.status_code} {h.headers.get('location', '')} ({len(h.text)} chars) {h.text[:120]!r}")
    for name, opts in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        vals = re.findall(r'value="([^"]*)"', opts)
        print(f"  select {name}: longest value {max((len(v) for v in vals), default=0)} chars")
    for name in re.findall(r'name="([^"]+)"', html):
        print("  field:", name)


def redact(folder: str) -> None:
    """Blank out anything that looks like a key, token or secret before the code is kept."""
    from pathlib import Path
    token = re.compile(r"sb_(?:publishable|secret)_[A-Za-z0-9_\-]+|eyJ[A-Za-z0-9_\-.]{20,}|re_[A-Za-z0-9_]{16,}|[A-Fa-f0-9]{32,}")
    named = re.compile(r"""((?i:secret|password|passwd|key|token)['"]?\s*(?:=>|=|:)\s*)(['"])[^'"]{8,}\2""")
    for f in Path(folder).glob("*.php"):
        src = f.read_text(encoding="utf-8", errors="replace")
        src, n1 = token.subn("[REMOVED]", src)
        src, n2 = named.subn(lambda m: m.group(1) + m.group(2) + "[REMOVED]" + m.group(2), src)
        f.write_text(src)
        print(f"{f.name}: {n1 + n2} value(s) removed")


if __name__ == "__main__":
    {"redact": lambda: redact(sys.argv[2]), "db": lambda: db(), "handler": lambda: handler(sys.argv[2]), "page": lambda: page()}[sys.argv[1]]()

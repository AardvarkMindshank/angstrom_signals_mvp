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


def page() -> None:
    html = requests.get("https://angstromsignals.com/beta.html", timeout=60).text
    print("form action:", re.findall(r'action="([^"]+)"', html))
    for name, opts in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        vals = re.findall(r'value="([^"]*)"', opts)
        print(f"  select {name}: longest value {max((len(v) for v in vals), default=0)} chars")
    for name in re.findall(r'name="([^"]+)"', html):
        print("  field:", name)


if __name__ == "__main__":
    {"db": lambda: db(), "handler": lambda: handler(sys.argv[2]), "page": lambda: page()}[sys.argv[1]]()

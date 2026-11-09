"""Writes sql/2026-11-15_provided_groups.sql: every Group the provided Sets use, as provided Groups (prism.provided_groups),
and analysis_rename_config (✏️ Rename for your own Groups and Sets).

Trend, Stretch and Flow get a new version with their labels (Bullish, Bearish …); Trend (weekly) and Recent structure
break are new. Running it twice changes nothing (analysis_seed_starter adds a version only when the body differs).

    python provided_groups_sql.py
"""

from __future__ import annotations

import json
from pathlib import Path

import prism

OUT = Path(__file__).resolve().parent / "sql" / "2026-11-15_provided_groups.sql"


RENAME = """create or replace function public.analysis_rename_config(cfg uuid, new_name text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    c public.analysis_configs;
    clean text := btrim(regexp_replace(coalesce(new_name, ''), '\\s+', ' ', 'g'));
begin
    select * into c from public.analysis_configs where id = cfg for update;
    if c.id is null or me is null or c.owner_id is distinct from me then raise exception 'not_owner'; end if;
    if c.archived then raise exception 'archived'; end if;
    if length(clean) < 1 or length(clean) > 80 then
        raise exception 'bad_name' using hint = 'A name needs 1 to 80 characters.';
    end if;
    if exists (select 1 from public.analysis_configs o
                where o.owner_id = me and o.kind = c.kind and not o.archived and o.id <> cfg
                  and lower(o.name) = lower(clean)) then
        raise exception 'name_taken' using hint = 'You already have one with that name.';
    end if;
    update public.analysis_configs set name = clean where id = cfg;
end;
$$;
revoke all on function public.analysis_rename_config(uuid, text) from public, anon;
grant execute on function public.analysis_rename_config(uuid, text) to authenticated;"""


def text() -> str:
    lines = ["-- Provided Groups used by the provided Sets, and renaming your own Groups and Sets",
             "-- (written by provided_groups_sql.py; do not edit by hand). Safe to run more than once.", "", RENAME, ""]
    for alias, (name, body) in prism.provided_groups().items():
        doc = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert "$json$" not in doc
        lines.append(f"select public.analysis_seed_starter('{alias}', $json${doc}$json$::jsonb);")
        safe = name.replace("'", "''")
        lines.append(f"update public.analysis_configs set name = '{safe}' where starter_alias = '{alias}';")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8")
    print(f"wrote {OUT}")

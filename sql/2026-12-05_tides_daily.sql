-- Tides daily readings for Sets and funnels (tides_history.py, 18 Nov 2026). Safe to run more than once. Adds one
-- table; changes nothing else. The background worker adds one row per finished US business day from 30 Oct 2024
-- (the days before that ship with the app, in data/tides_history.csv.gz). Rows are only ever added, never changed:
-- first_seen_at is set by the database, so replays only count what had really been saved by then.

create table if not exists public.tides_daily (
    day date primary key,
    body jsonb not null,
    first_seen_at timestamptz not null default now()
);

create or replace function public.tides_daily_first_seen()
returns trigger
language plpgsql
as $$
begin
    new.first_seen_at := now();
    return new;
end;
$$;

drop trigger if exists tides_daily_first_seen on public.tides_daily;
create trigger tides_daily_first_seen before insert on public.tides_daily
    for each row execute function public.tides_daily_first_seen();

alter table public.tides_daily enable row level security;

-- Market-wide readings, no personal data: readable before sign-in too.
drop policy if exists "anyone reads tides daily" on public.tides_daily;
create policy "anyone reads tides daily" on public.tides_daily
    for select
    to anon, authenticated
    using (true);

grant select on public.tides_daily to anon, authenticated;

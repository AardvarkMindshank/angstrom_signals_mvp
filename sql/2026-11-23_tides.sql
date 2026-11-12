-- Tides: the daily macro record (tides.py). Safe to run more than once. Adds one table; changes nothing else.
-- The background worker saves a snapshot every 6 hours: every current's reading, the Tide, the Sea state and the
-- winds. Rows are never changed (append-only). first_seen_at is set by the database, so later replays only count
-- what had really been recorded by then: the point-in-time history of Tides starts with the first row.

create table if not exists public.tides_snapshots (
    id bigserial primary key,
    computed_at timestamptz not null,
    version integer not null,
    body jsonb not null,
    first_seen_at timestamptz not null default now()
);

create index if not exists tides_snapshots_time on public.tides_snapshots (computed_at desc);

create or replace function public.tides_first_seen()
returns trigger
language plpgsql
as $$
begin
    new.first_seen_at := now();
    return new;
end;
$$;

drop trigger if exists tides_first_seen on public.tides_snapshots;
create trigger tides_first_seen before insert on public.tides_snapshots
    for each row execute function public.tides_first_seen();

alter table public.tides_snapshots enable row level security;

drop policy if exists "signed-in users read tides" on public.tides_snapshots;
create policy "signed-in users read tides" on public.tides_snapshots
    for select
    to authenticated
    using (true);

grant select on public.tides_snapshots to authenticated;

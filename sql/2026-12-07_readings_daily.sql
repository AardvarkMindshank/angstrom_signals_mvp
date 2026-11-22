-- The daily readings record (22 Nov 2026, Trade Logbook spec). Safe to run more than once. Adds one table; changes
-- nothing else. The background worker (stored_readings.py) adds one row per asset per finished day with the headline
-- readings MarketNavi showed: Trend, Stretch, Flow and the regime. About 150 bytes a row, roughly 40 MB a year.
-- Rows are only ever added, never changed: the first reading saved for a day stands, and first_seen_at is set by the
-- database, so a trade's snapshot can say what MarketNavi had really shown by then ("observed").

create table if not exists public.readings_daily (
    asset_key text not null check (char_length(asset_key) between 3 and 80),   -- "crypto:bitcoin", "equity:AAPL"
    day date not null,                                                       -- the finished daily bar read
    trend numeric,
    stretch numeric,
    flow numeric,
    regime text check (regime is null or char_length(regime) <= 40),
    version text not null default '' check (char_length(version) <= 64),     -- the readings' definition fingerprint
    first_seen_at timestamptz not null default now(),
    primary key (asset_key, day)
);

create or replace function public.readings_daily_first_seen()
returns trigger
language plpgsql
as $$
begin
    new.first_seen_at := now();
    return new;
end;
$$;

drop trigger if exists readings_daily_first_seen on public.readings_daily;
create trigger readings_daily_first_seen before insert on public.readings_daily
    for each row execute function public.readings_daily_first_seen();

alter table public.readings_daily enable row level security;

-- Market-wide readings, no personal data. Only the worker (the service role) writes; signed-in accounts may read.
drop policy if exists "signed-in accounts read the readings record" on public.readings_daily;
create policy "signed-in accounts read the readings record" on public.readings_daily
    for select
    to authenticated
    using (true);

revoke all on public.readings_daily from public, anon;
grant select on public.readings_daily to authenticated;

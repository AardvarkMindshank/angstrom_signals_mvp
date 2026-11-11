-- Options max-pain snapshots: the history behind the max pain signal (signal_library/signals_options.py).
-- Safe to run more than once. Adds one table; changes nothing else.
--
-- Nobody publishes past open interest by strike, so the background worker records it (options_snapshots.py):
-- Bitcoin and Ethereum from Deribit every 4 hours, watched and funnel equities from Yahoo once per trading day.
-- One row per asset, expiry and snapshot. Rows are never changed or deleted (append-only).
-- first_seen_at is set by the database on insert and cannot be supplied by the caller (the trigger overwrites it),
-- so a replay at time T only counts what the database really had by T.

create table if not exists public.options_pain (
    asset_key text not null,                 -- Crypto|bitcoin, Crypto|ethereum, Stock|AAPL
    recorded_at timestamptz not null,        -- when the snapshot was taken
    expiry date not null,
    spot numeric,                            -- the underlying price at the snapshot
    max_pain numeric not null,
    call_oi numeric,
    put_oi numeric,
    strikes integer,
    source text,
    first_seen_at timestamptz not null default now(),
    primary key (asset_key, expiry, recorded_at)
);

create index if not exists options_pain_asset_time on public.options_pain (asset_key, recorded_at desc);

create or replace function public.options_pain_first_seen()
returns trigger
language plpgsql
as $$
begin
    new.first_seen_at := now();
    return new;
end;
$$;

drop trigger if exists options_pain_first_seen on public.options_pain;
create trigger options_pain_first_seen before insert on public.options_pain
    for each row execute function public.options_pain_first_seen();

-- Signed-in users may read; only the background worker (service role) writes.
alter table public.options_pain enable row level security;

drop policy if exists "signed-in users read options snapshots" on public.options_pain;
create policy "signed-in users read options snapshots" on public.options_pain
    for select
    to authenticated
    using (true);

grant select on public.options_pain to authenticated;

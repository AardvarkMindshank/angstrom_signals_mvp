-- Observed capital flows (collection only). Safe to run more than once. Adds two tables; changes nothing else.
-- Written only by the background worker (service role). Signed-in users may read; nothing is shown in the
-- app yet. See capital_flows.py for the sources and their licence terms.

-- One row per source, series, subject, day and value. A revised value is a new row, so the first
-- published value is the one with the earliest fetched_at. Rows from a first-run history load are
-- marked backfilled: their fetched_at is not when the value was really available.
create table if not exists public.capital_flow_observations (
    source text not null,
    series text not null,
    subject text not null,
    observed_date date not null,
    value numeric not null,
    unit text not null default 'USD',
    kind text,
    fetched_at timestamptz not null default now(),
    backfilled boolean not null default false,
    primary key (source, series, subject, observed_date, value)
);

create index if not exists capital_flow_observations_lookup
    on public.capital_flow_observations (source, series, subject, observed_date desc);

alter table public.capital_flow_observations enable row level security;

drop policy if exists "signed-in users read capital flows" on public.capital_flow_observations;
create policy "signed-in users read capital flows" on public.capital_flow_observations
    for select
    to authenticated
    using (true);

grant select on public.capital_flow_observations to authenticated;

-- Every fetch the worker makes, successful or not: the refresh clock and an audit trail.
create table if not exists public.capital_flow_fetches (
    id bigint generated always as identity primary key,
    source text not null,
    fetched_at timestamptz not null default now(),
    ok boolean not null,
    rows_sent integer not null default 0,
    latest_date date,
    note text
);

create index if not exists capital_flow_fetches_recent
    on public.capital_flow_fetches (source, fetched_at desc);

alter table public.capital_flow_fetches enable row level security;
revoke all on public.capital_flow_fetches from anon;
revoke all on public.capital_flow_fetches from authenticated;

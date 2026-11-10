-- The funnel: a dynamic watchlist in stages (decision: docs/research/funnel_brief_2026-11-10.md, "Decision after
-- review"). Safe to run more than once. Adds four tables and three functions; changes nothing that exists.
--
--  * crypto_universe   the coins a funnel may check (CoinGecko's top coins on Binance spot, with the quality gate),
--                      written by the crypto-universe job; every coin left out keeps its reason. Everyone signed in
--                      reads it.
--  * funnels           an account's funnels: a direction (long or short) and 3 to 5 stages, each a pinned copy of
--                      one Set version on its own timeframe. At most 4 funnels per account.
--  * funnel_coins      each coin's place in a funnel (funnel.py's CoinState), written by the funnel job only.
--  * funnel_runs       one row per (funnel, stage, candle close): the job's claim, so a retry never repeats a run
--                      or its alerts.
-- Signed-in users never write these tables directly: changes go through the functions. Owners read their own rows.

create table if not exists public.crypto_universe (
    coin_id text primary key check (char_length(coin_id) between 1 and 120),
    symbol text not null default '',
    name text not null default '',
    rank integer,
    included boolean not null,
    pair text,                                   -- the Binance spot pair, e.g. BTCUSDT (included coins)
    reason text,                                 -- why a coin is left out
    volume_usd numeric,                          -- median daily USDT traded on Binance, last 30 closed days
    listed_since date,
    built_at timestamptz not null default now()
);

create table if not exists public.funnels (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users (id) on delete cascade,
    name text not null check (char_length(btrim(name)) between 1 and 80),
    direction text not null check (direction in ('long', 'short')),
    stages jsonb not null,                       -- [{label, timeframe, set_body, set_source}], 3 to 5
    flicker boolean not null default true,       -- leave a stage only after two No closes in a row
    alerts jsonb not null default '{"in_app": true, "email": false}'::jsonb,
    paused boolean not null default false,
    stages_version integer not null default 1,   -- bumped when the stages change; coins then start again
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.funnel_coins (
    funnel_id uuid not null references public.funnels (id) on delete cascade,
    coin_id text not null,
    stages_version integer not null,
    state jsonb not null,
    status text not null default 'pool' check (status in ('pool', 'stage', 'flagged', 'candidate')),
    depth integer not null default 0,
    pending boolean not null default false,
    updated_at timestamptz not null default now(),
    primary key (funnel_id, coin_id)
);

create table if not exists public.funnel_runs (
    id bigint generated always as identity primary key,
    funnel_id uuid not null references public.funnels (id) on delete cascade,
    stage integer not null check (stage between 0 and 4),
    cutoff timestamptz not null,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'running' check (status in ('running', 'ok', 'failed')),
    checked integer,
    answers jsonb,                               -- {yes, no, unknown} counts
    error text check (error is null or char_length(error) <= 500),
    unique (funnel_id, stage, cutoff)
);

create index if not exists funnels_owner on public.funnels (owner_id);
create index if not exists funnel_coins_status on public.funnel_coins (funnel_id, status);
create index if not exists funnel_runs_funnel on public.funnel_runs (funnel_id, cutoff desc);

alter table public.crypto_universe enable row level security;
alter table public.funnels enable row level security;
alter table public.funnel_coins enable row level security;
alter table public.funnel_runs enable row level security;

drop policy if exists "signed-in accounts read the crypto universe" on public.crypto_universe;
create policy "signed-in accounts read the crypto universe" on public.crypto_universe
    for select to authenticated using (true);
drop policy if exists "owners read their funnels" on public.funnels;
create policy "owners read their funnels" on public.funnels
    for select to authenticated using (owner_id = auth.uid());
drop policy if exists "owners read their funnel coins" on public.funnel_coins;
create policy "owners read their funnel coins" on public.funnel_coins
    for select to authenticated
    using (exists (select 1 from public.funnels f where f.id = funnel_id and f.owner_id = auth.uid()));
drop policy if exists "owners read their funnel runs" on public.funnel_runs;
create policy "owners read their funnel runs" on public.funnel_runs
    for select to authenticated
    using (exists (select 1 from public.funnels f where f.id = funnel_id and f.owner_id = auth.uid()));

revoke all on public.crypto_universe, public.funnels, public.funnel_coins, public.funnel_runs from anon, authenticated;
grant select on public.crypto_universe, public.funnels, public.funnel_coins, public.funnel_runs to authenticated;

-- Create (p_id null) or change one of your funnels. Returns its id. The job validates every Set again before each
-- run; this checks shape, size and limits. Changing the stages starts every coin again from the pool.
create or replace function public.funnel_save(p_id uuid, p_name text, p_direction text, p_stages jsonb,
                                              p_flicker boolean, p_alerts jsonb, p_paused boolean)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    fid uuid;
    old_stages jsonb;
    stage jsonb;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    if not (p_direction in ('long', 'short')) then raise exception 'bad_direction'; end if;
    if p_stages is null or jsonb_typeof(p_stages) <> 'array' or jsonb_array_length(p_stages) not between 3 and 5 then
        raise exception 'bad_stages';
    end if;
    for stage in select * from jsonb_array_elements(p_stages) loop
        if not (stage->>'timeframe' in ('15m', '30m', '1h', '4h', '12h', '1D', '1W'))
           or stage->'set_body'->>'schema' <> 'angstrom.set/1' or not (stage->'set_body' ? 'decision') then
            raise exception 'bad_stages';
        end if;
    end loop;
    if pg_column_size(p_stages) > 524288 then raise exception 'too_large'; end if;

    if p_id is null then
        if (select count(*) from public.funnels where owner_id = me) >= 4 then raise exception 'too_many_funnels'; end if;
        insert into public.funnels (owner_id, name, direction, stages, flicker, alerts, paused)
        values (me, btrim(p_name), p_direction, p_stages, coalesce(p_flicker, true),
                coalesce(p_alerts, '{"in_app": true, "email": false}'::jsonb), coalesce(p_paused, false))
        returning id into fid;
        return fid;
    end if;

    select stages into old_stages from public.funnels where id = p_id and owner_id = me;
    if not found then raise exception 'not_owner'; end if;
    update public.funnels
       set name = btrim(p_name), direction = p_direction, stages = p_stages, flicker = coalesce(p_flicker, flicker),
           alerts = coalesce(p_alerts, alerts), paused = coalesce(p_paused, paused),
           stages_version = stages_version + (case when old_stages = p_stages then 0 else 1 end),
           updated_at = now()
     where id = p_id and owner_id = me;
    return p_id;
end;
$$;

create or replace function public.funnel_delete(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.funnels where id = p_id and owner_id = auth.uid() and auth.uid() is not null;
    if not found then raise exception 'not_owner'; end if;
end;
$$;

-- Start every coin again from the pool (for example after changing a stage's Set outside the funnel).
create or replace function public.funnel_restart(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not exists (select 1 from public.funnels where id = p_id and owner_id = auth.uid() and auth.uid() is not null)
    then raise exception 'not_owner'; end if;
    delete from public.funnel_coins where funnel_id = p_id;
    update public.funnels set stages_version = stages_version + 1, updated_at = now() where id = p_id;
end;
$$;

revoke all on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean),
    public.funnel_delete(uuid), public.funnel_restart(uuid) from public, anon;
grant execute on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean),
    public.funnel_delete(uuid), public.funnel_restart(uuid) to authenticated;

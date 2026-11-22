-- Trade Log (22 Nov 2026, spec v0.5): a member's closed trades from eToro (Binance later), each with what MarketNavi
-- read at entry and exit. Safe to run more than once. Adds four tables and four functions; changes nothing else.
--
-- Broker keys are never stored in a table. They go into Supabase Vault (encrypted by Supabase), and the connection
-- row keeps only the Vault secret's id. A signed-in member can save, list and delete their own connections, but
-- only the server (the service role, used by the sync worker) can read a key back. Keys are read-only keys.
--
-- Trades, snapshots and coaching are written by the server only; members read their own. Notes and tags are the
-- member's own and they can edit them. Deleting a connection deletes its trades (cascade) and its Vault secret.

create table if not exists public.trade_connections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    platform text not null check (platform in ('etoro', 'binance')),
    label text not null default '' check (char_length(label) <= 60),
    secret_id uuid not null,
    status text not null default 'new' check (status in ('new', 'importing', 'ok', 'failing', 'paused')),
    last_sync_at timestamptz,
    last_error text not null default '' check (char_length(last_error) <= 300),
    history_from date,
    created_at timestamptz not null default now()
);

create index if not exists trade_connections_user on public.trade_connections (user_id);

alter table public.trade_connections enable row level security;

drop policy if exists "own trade connections" on public.trade_connections;
create policy "own trade connections" on public.trade_connections
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_connections from public, anon;
grant select on public.trade_connections to authenticated;


create table if not exists public.trade_round_trips (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    connection_id uuid not null references public.trade_connections (id) on delete cascade,
    platform text not null,
    position_id text not null check (char_length(position_id) <= 40),
    instrument_id text not null default '',
    symbol text not null default '' check (char_length(symbol) <= 40),
    name text not null default '' check (char_length(name) <= 120),
    asset_class text not null default 'other'
        check (asset_class in ('crypto', 'stocks', 'etfs', 'indices', 'commodities', 'currencies', 'other')),
    asset_key text,                                                   -- MarketNavi's key, when the asset is listed
    direction text not null check (direction in ('long', 'short')),
    opened_at timestamptz not null,
    closed_at timestamptz not null,
    entry_price numeric,
    exit_price numeric,
    units numeric,
    invested_usd numeric,
    leverage numeric not null default 1,
    fees_usd numeric,
    net_result_usd numeric,
    result_pct numeric,
    copied boolean not null default false,
    parts integer not null default 1,                                 -- broker positions merged into this one
    imported_at timestamptz not null default now(),
    unique (connection_id, position_id)
);

create index if not exists trade_round_trips_user_closed on public.trade_round_trips (user_id, closed_at desc);

alter table public.trade_round_trips enable row level security;

drop policy if exists "own round trips" on public.trade_round_trips;
create policy "own round trips" on public.trade_round_trips
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_round_trips from public, anon;
grant select on public.trade_round_trips to authenticated;


create table if not exists public.trade_snapshots (
    round_trip_id bigint not null references public.trade_round_trips (id) on delete cascade,
    moment text not null check (moment in ('entry', 'exit')),
    user_id uuid not null references auth.users (id) on delete cascade,
    readings jsonb not null default '{}'::jsonb check (pg_column_size(readings) < 20000),
    source text not null default 'reconstructed' check (source in ('observed', 'reconstructed', 'unavailable')),
    definitions text not null default '' check (char_length(definitions) <= 64),
    computed_at timestamptz not null default now(),
    primary key (round_trip_id, moment)
);

alter table public.trade_snapshots enable row level security;

drop policy if exists "own trade snapshots" on public.trade_snapshots;
create policy "own trade snapshots" on public.trade_snapshots
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_snapshots from public, anon;
grant select on public.trade_snapshots to authenticated;


create table if not exists public.trade_notes (
    round_trip_id bigint primary key references public.trade_round_trips (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    note text not null default '' check (char_length(note) <= 2000),
    tags text[] not null default '{}' check (cardinality(tags) <= 12),
    updated_at timestamptz not null default now()
);

alter table public.trade_notes enable row level security;

drop policy if exists "own trade notes" on public.trade_notes;
create policy "own trade notes" on public.trade_notes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (
        auth.uid() = user_id
        and exists (select 1 from public.trade_round_trips as t
                    where t.id = trade_notes.round_trip_id and t.user_id = auth.uid())
    );

revoke all on public.trade_notes from public, anon;
grant select, insert, update, delete on public.trade_notes to authenticated;


-- Save a connection: the keys go straight into Vault; the row keeps only the secret's id.
create or replace function public.tradelog_save_connection(p_platform text, p_label text, p_keys jsonb)
returns uuid
language plpgsql
security definer
set search_path = public, vault
as $$
declare
    who uuid := auth.uid();
    sid uuid;
    cid uuid := gen_random_uuid();
begin
    if who is null then
        raise exception 'sign in first';
    end if;
    if p_platform not in ('etoro', 'binance') then
        raise exception 'unknown platform';
    end if;
    if jsonb_typeof(p_keys) <> 'object' or pg_column_size(p_keys) > 4000 then
        raise exception 'keys must be a small object';
    end if;
    if (select count(*) from public.trade_connections where user_id = who) >= 10 then
        raise exception 'too many connections';
    end if;
    sid := vault.create_secret(p_keys::text, 'tradelog_' || cid::text, 'Trade Log read-only broker key');
    insert into public.trade_connections (id, user_id, platform, label, secret_id)
    values (cid, who, p_platform, left(coalesce(p_label, ''), 60), sid);
    return cid;
end;
$$;

revoke all on function public.tradelog_save_connection(text, text, jsonb) from public, anon;
grant execute on function public.tradelog_save_connection(text, text, jsonb) to authenticated;


-- Disconnect: deletes the Vault secret, the connection and (cascade) its trades, snapshots and notes.
create or replace function public.tradelog_delete_connection(p_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public, vault
as $$
declare
    sid uuid;
begin
    select secret_id into sid from public.trade_connections where id = p_id and user_id = auth.uid();
    if sid is null then
        return false;
    end if;
    delete from public.trade_connections where id = p_id;
    delete from vault.secrets where id = sid;
    return true;
end;
$$;

revoke all on function public.tradelog_delete_connection(uuid) from public, anon;
grant execute on function public.tradelog_delete_connection(uuid) to authenticated;


-- Read a connection's keys back: the server only (the sync worker), never a signed-in member.
create or replace function public.tradelog_connection_keys(p_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, vault
as $$
declare
    body text;
begin
    select s.decrypted_secret into body
      from public.trade_connections c
      join vault.decrypted_secrets s on s.id = c.secret_id
     where c.id = p_id;
    return case when body is null then null else body::jsonb end;
end;
$$;

revoke all on function public.tradelog_connection_keys(uuid) from public, anon, authenticated;
grant execute on function public.tradelog_connection_keys(uuid) to service_role;


-- Delete all my Trade Log data (Settings): every connection, its keys, trades, snapshots and notes.
create or replace function public.tradelog_delete_everything()
returns integer
language plpgsql
security definer
set search_path = public, vault
as $$
declare
    n integer := 0;
    r record;
begin
    for r in select id, secret_id from public.trade_connections where user_id = auth.uid() loop
        delete from public.trade_connections where id = r.id;
        delete from vault.secrets where id = r.secret_id;
        n := n + 1;
    end loop;
    return n;
end;
$$;

revoke all on function public.tradelog_delete_everything() from public, anon;
grant execute on function public.tradelog_delete_everything() to authenticated;

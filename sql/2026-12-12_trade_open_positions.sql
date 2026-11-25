-- Trade Log open positions (26 Nov 2026). Safe to run more than once. Adds one table and three columns.
-- eToro's trade history holds closed trades only. The sync now also reads the account's current portfolio
-- (trading/info/real/pnl) and keeps the open positions here, replaced at each sync, plus the spare cash and open
-- profit or loss on the connection. Members read only their own rows; only the sync (service role) writes.

create table if not exists public.trade_open_positions (
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
    asset_key text,
    direction text not null check (direction in ('long', 'short')),
    opened_at timestamptz,
    entry_price numeric,
    current_price numeric,
    units numeric,
    invested_usd numeric,
    value_usd numeric,
    pnl_usd numeric,
    leverage numeric not null default 1,
    copied boolean not null default false,
    read_at timestamptz not null default now(),
    unique (connection_id, position_id)
);

create index if not exists trade_open_positions_user on public.trade_open_positions (user_id);

alter table public.trade_open_positions enable row level security;

drop policy if exists "own open positions" on public.trade_open_positions;
create policy "own open positions" on public.trade_open_positions
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_open_positions from public, anon;
grant select on public.trade_open_positions to authenticated;

alter table public.trade_connections add column if not exists cash_usd numeric;
alter table public.trade_connections add column if not exists open_pnl_usd numeric;
alter table public.trade_connections add column if not exists portfolio_at timestamptz;

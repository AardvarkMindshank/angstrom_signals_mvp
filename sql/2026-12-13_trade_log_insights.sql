-- Trade Log insights (26 Nov 2026). Safe to run more than once. Adds two tables and some columns.
-- For the new Trade Log page: eToro's daily return and allocation history (trade_series), each trade's stop loss,
-- take profit and how it ended, and ready-made summaries the page reads in one go (trade_insights). The background
-- job (service role) writes all of it; members read only their own rows.

-- Each closed trade: the stop loss, take profit and trailing stop set on it, how it ended, its result in units of
-- risk (R), how much of the best price move it kept and what the price did in the 20 days after.
alter table public.trade_round_trips add column if not exists stop_loss numeric;
alter table public.trade_round_trips add column if not exists take_profit numeric;
alter table public.trade_round_trips add column if not exists trailing_stop boolean;
alter table public.trade_round_trips add column if not exists exit_kind text
    check (exit_kind is null or exit_kind in ('stop_loss', 'take_profit', 'trailing_stop', 'by_hand'));
alter table public.trade_round_trips add column if not exists risk_r numeric;
alter table public.trade_round_trips add column if not exists kept_pct numeric;
alter table public.trade_round_trips add column if not exists after20_pct numeric;
alter table public.trade_round_trips add column if not exists moves_checked boolean not null default false;

-- Open positions: stop loss and overnight fees.
alter table public.trade_open_positions add column if not exists stop_loss numeric;
alter table public.trade_open_positions add column if not exists overnight_fees_usd numeric;

-- Account-level series from eToro, one row per connection and kind ('daily_gain', 'allocation').
create table if not exists public.trade_series (
    connection_id uuid not null references public.trade_connections (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    kind text not null check (kind in ('daily_gain', 'allocation', 'benchmarks')),
    data jsonb not null check (pg_column_size(data) < 2000000),
    read_at timestamptz not null default now(),
    primary key (connection_id, kind)
);

alter table public.trade_series enable row level security;

drop policy if exists "own trade series" on public.trade_series;
create policy "own trade series" on public.trade_series
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_series from public, anon;
grant select on public.trade_series to authenticated;

-- Ready-made summaries for the page: one row per member, scope ('all' or a connection id), whose ('own', 'copied',
-- 'all') and period ('1y', '3y', '5y', 'all').
create table if not exists public.trade_insights (
    user_id uuid not null references auth.users (id) on delete cascade,
    scope text not null check (char_length(scope) <= 40),
    whose text not null check (whose in ('own', 'copied', 'all')),
    period text not null check (period in ('1y', '3y', '5y', 'all')),
    data jsonb not null check (pg_column_size(data) < 1000000),
    computed_at timestamptz not null default now(),
    primary key (user_id, scope, whose, period)
);

alter table public.trade_insights enable row level security;

drop policy if exists "own trade insights" on public.trade_insights;
create policy "own trade insights" on public.trade_insights
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.trade_insights from public, anon;
grant select on public.trade_insights to authenticated;

-- When the insights were last worked out, so the job knows when to work them out again.
alter table public.trade_connections add column if not exists insights_at timestamptz;

-- "Delete all my Trade Log data" also removes the summaries (the series go with their connection).
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
    delete from public.trade_reviews where user_id = auth.uid();
    delete from public.trade_insights where user_id = auth.uid();
    return n;
end;
$$;

revoke all on function public.tradelog_delete_everything() from public, anon;
grant execute on function public.tradelog_delete_everything() to authenticated;

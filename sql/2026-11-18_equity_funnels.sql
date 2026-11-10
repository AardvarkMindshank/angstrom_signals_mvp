-- Funnels for equities (asked 10 Nov 2026). Safe to run more than once. Needs sql/2026-11-17_funnels.sql first.
--
--  * equity_universe   the shares an equity funnel may check (the S&P 500 with a quality gate), written by the
--                      equity-universe job; every share left out keeps its reason. Everyone signed in reads it.
--  * funnels.market    'crypto' (every funnel so far) or 'equity'.
--  * funnel_save       takes the market too (the old 7-argument version still works and saves a crypto funnel).

create table if not exists public.equity_universe (
    ticker text primary key check (char_length(ticker) between 1 and 12),
    name text not null default '',
    sector text,
    rank integer,                                -- by market cap within the list
    included boolean not null,
    reason text,
    volume_usd numeric,                          -- median daily dollar volume, last 30 sessions
    price numeric,
    next_earnings date,
    built_at timestamptz not null default now()
);

alter table public.equity_universe enable row level security;
drop policy if exists "signed-in accounts read the equity universe" on public.equity_universe;
create policy "signed-in accounts read the equity universe" on public.equity_universe
    for select to authenticated using (true);
revoke all on public.equity_universe from anon, authenticated;
grant select on public.equity_universe to authenticated;

alter table public.funnels add column if not exists market text not null default 'crypto';
alter table public.funnels drop constraint if exists funnels_market_check;
alter table public.funnels add constraint funnels_market_check check (market in ('crypto', 'equity'));

create or replace function public.funnel_save(p_id uuid, p_name text, p_direction text, p_stages jsonb,
                                              p_flicker boolean, p_alerts jsonb, p_paused boolean, p_market text)
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
    if not (coalesce(p_market, 'crypto') in ('crypto', 'equity')) then raise exception 'bad_market'; end if;
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
        if (select count(*) from public.funnels where owner_id = me) >= 6 then raise exception 'too_many_funnels'; end if;
        insert into public.funnels (owner_id, name, direction, stages, flicker, alerts, paused, market)
        values (me, btrim(p_name), p_direction, p_stages, coalesce(p_flicker, true),
                coalesce(p_alerts, '{"in_app": true, "email": false}'::jsonb), coalesce(p_paused, false),
                coalesce(p_market, 'crypto'))
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
     where id = p_id and owner_id = me;            -- the market of an existing funnel never changes
    return p_id;
end;
$$;

revoke all on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean, text) from public, anon;
grant execute on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean, text) to authenticated;

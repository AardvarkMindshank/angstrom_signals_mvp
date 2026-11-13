-- ✏️ Chart drawings (13 Nov 2026): lines, shapes, pen strokes and notes drawn on the price chart, saved to the account.
-- One row per account and asset (key "crypto:bitcoin", "equity:AAPL"), so a drawing shows on every candle size.
-- Points are stored as (time in seconds, price), so drawings stay put when the chart zooms or scrolls.
-- The chart saves straight from the browser with the signed-in person's own session (row-level security: own rows).
--
-- Sharing: chart_shares holds a copy of the drawings shared with one or more of your communities, with a short note.
-- Members of those communities can see it (and get a notification); the person who shared it can delete it.
--
-- Safe to run more than once. Adds two tables and one function; changes nothing else.

create table if not exists public.chart_drawings (
    user_id uuid not null references auth.users (id) on delete cascade,
    asset_key text not null check (char_length(asset_key) between 3 and 80),
    items jsonb not null default '[]'::jsonb check (jsonb_typeof(items) = 'array'),
    updated_at timestamptz not null default now(),
    primary key (user_id, asset_key)
);

alter table public.chart_drawings enable row level security;

drop policy if exists "own chart drawings" on public.chart_drawings;
create policy "own chart drawings" on public.chart_drawings
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id and pg_column_size(items) < 400000);

grant select, insert, update, delete on public.chart_drawings to authenticated;


create table if not exists public.chart_shares (
    id bigint generated always as identity primary key,
    owner_id uuid not null references auth.users (id) on delete cascade,
    asset_key text not null,
    asset_name text not null default '',
    timeframe text not null default '',
    items jsonb not null default '[]'::jsonb check (jsonb_typeof(items) = 'array'),
    note text not null default '' check (char_length(note) <= 160),
    group_ids bigint[] not null,
    created_at timestamptz not null default now()
);

create index if not exists chart_shares_owner on public.chart_shares (owner_id, created_at desc);

alter table public.chart_shares enable row level security;

drop policy if exists "see chart shares" on public.chart_shares;
create policy "see chart shares" on public.chart_shares
    for select
    to authenticated
    using (
        owner_id = auth.uid()
        or exists (
            select 1 from public.user_groups as groups
            where groups.id = any (chart_shares.group_ids)
              and (
                  groups.leader_id = auth.uid()
                  or exists (select 1 from public.group_members as members
                             where members.group_id = groups.id and members.user_id = auth.uid())
              )
        )
    );

drop policy if exists "delete own chart shares" on public.chart_shares;
create policy "delete own chart shares" on public.chart_shares
    for delete
    to authenticated
    using (owner_id = auth.uid());

grant select, delete on public.chart_shares to authenticated;

-- Share drawings with communities you lead or belong to; every other member of them gets a notification.
create or replace function public.share_chart(
    p_asset_key text,
    p_asset_name text,
    p_timeframe text,
    p_items jsonb,
    p_note text,
    p_groups bigint[]
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    allowed bigint[];
    share_id bigint;
    who text;
    where_words text;
begin
    if me is null then
        raise exception 'not signed in';
    end if;
    if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception 'nothing to share';
    end if;
    if pg_column_size(p_items) > 400000 then
        raise exception 'too large';
    end if;
    select array_agg(groups.id) into allowed
    from public.user_groups as groups
    where groups.id = any (coalesce(p_groups, '{}'))
      and (groups.leader_id = me
           or exists (select 1 from public.group_members as members
                      where members.group_id = groups.id and members.user_id = me));
    if allowed is null or cardinality(allowed) = 0 then
        raise exception 'choose a community you belong to';
    end if;

    insert into public.chart_shares (owner_id, asset_key, asset_name, timeframe, items, note, group_ids)
    values (me, left(coalesce(p_asset_key, ''), 80), left(coalesce(p_asset_name, ''), 80),
            left(coalesce(p_timeframe, ''), 8), p_items, left(btrim(coalesce(p_note, '')), 160), allowed)
    returning id into share_id;

    select coalesce(nullif(btrim(profiles.display_name), ''), nullif(split_part(users.email, '@', 1), ''), 'Someone')
      into who
    from auth.users as users
    left join public.profiles as profiles on profiles.user_id = users.id
    where users.id = me;

    select string_agg(groups.name, ', ' order by groups.name) into where_words
    from public.user_groups as groups where groups.id = any (allowed);

    insert into public.user_notifications (user_id, asset_symbol, asset_name, alert_type, message)
    select distinct people.person, 'chartshare:' || share_id, left(coalesce(p_asset_name, ''), 80), 'chart_share',
           left(who || ' shared a chart of ' || coalesce(nullif(p_asset_name, ''), 'an asset') || ' with drawings in '
                || where_words || case when btrim(coalesce(p_note, '')) <> ''
                                       then ': "' || btrim(p_note) || '"' else '.' end, 500)
    from (
        select groups.leader_id as person from public.user_groups as groups where groups.id = any (allowed)
        union
        select members.user_id from public.group_members as members where members.group_id = any (allowed)
    ) as people
    where people.person <> me;

    return share_id;
end;
$$;

revoke all on function public.share_chart(text, text, text, jsonb, text, bigint[]) from public;
revoke all on function public.share_chart(text, text, text, jsonb, text, bigint[]) from anon;
grant execute on function public.share_chart(text, text, text, jsonb, text, bigint[]) to authenticated;

-- 👥 Members list for admins (19 Nov 2026). Run in Supabase → SQL Editor. Safe to run more than once.
--
-- 1. user_activity: one row per account, kept up to date by the app while the account has it open
--    (a small "still here" call about every 2 minutes). Nobody can read or write it directly.
-- 2. touch_activity(): the "still here" call. It only ever changes the caller's own row.
-- 3. ai_usage + log_ai_use(): the AI tokens each account's questions used, per day and model (the AI Navigator and
--    the Passage Plan). Only the caller's own row is ever added to; nobody can read it directly.
-- 4. admin_members(): every account with its plan, sign-up, last sign-in, last seen, how much it uses the app and
--    its AI use. Admins only.

create table if not exists public.user_activity (
    user_id uuid primary key references auth.users (id) on delete cascade,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    visits integer not null default 1,          -- a new visit after 30 minutes away
    active_days integer not null default 1,     -- days (UTC) with any use
    seconds bigint not null default 0           -- time with the app open (gaps over 10 minutes not counted)
);

alter table public.user_activity enable row level security;
revoke all on public.user_activity from anon, authenticated;
grant all on public.user_activity to service_role;

create or replace function public.touch_activity()
returns void
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    at_now timestamptz := now();
begin
    if me is null then
        return;
    end if;
    insert into public.user_activity as a (user_id) values (me)
    on conflict (user_id) do update set
        visits = a.visits + case when at_now - a.last_seen_at > interval '30 minutes' then 1 else 0 end,
        active_days = a.active_days
            + case when (at_now at time zone 'UTC')::date > (a.last_seen_at at time zone 'UTC')::date then 1 else 0 end,
        seconds = a.seconds
            + case when at_now - a.last_seen_at <= interval '10 minutes'
                   then greatest(0, extract(epoch from at_now - a.last_seen_at))::bigint else 0 end,
        last_seen_at = at_now;
end;
$$;

revoke all on function public.touch_activity() from public, anon;
grant execute on function public.touch_activity() to authenticated;

create table if not exists public.ai_usage (
    user_id uuid not null references auth.users (id) on delete cascade,
    day date not null default ((now() at time zone 'UTC')::date),
    provider text not null,
    model text not null,
    calls integer not null default 0,
    input_tokens bigint not null default 0,
    output_tokens bigint not null default 0,
    cache_read_tokens bigint not null default 0,
    cache_write_tokens bigint not null default 0,
    primary key (user_id, day, provider, model)
);

alter table public.ai_usage enable row level security;
revoke all on public.ai_usage from anon, authenticated;
grant all on public.ai_usage to service_role;

create or replace function public.log_ai_use(p_provider text, p_model text, p_input bigint, p_output bigint,
                                             p_cache_read bigint, p_cache_write bigint)
returns void
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    if me is null then
        return;
    end if;
    insert into public.ai_usage as a (user_id, provider, model, calls, input_tokens, output_tokens,
                                      cache_read_tokens, cache_write_tokens)
    values (me, left(coalesce(p_provider, '?'), 20), left(coalesce(p_model, '?'), 60), 1,
            greatest(coalesce(p_input, 0), 0), greatest(coalesce(p_output, 0), 0),
            greatest(coalesce(p_cache_read, 0), 0), greatest(coalesce(p_cache_write, 0), 0))
    on conflict (user_id, day, provider, model) do update set
        calls = a.calls + 1,
        input_tokens = a.input_tokens + excluded.input_tokens,
        output_tokens = a.output_tokens + excluded.output_tokens,
        cache_read_tokens = a.cache_read_tokens + excluded.cache_read_tokens,
        cache_write_tokens = a.cache_write_tokens + excluded.cache_write_tokens;
end;
$$;

revoke all on function public.log_ai_use(text, text, bigint, bigint, bigint, bigint) from public, anon;
grant execute on function public.log_ai_use(text, text, bigint, bigint, bigint, bigint) to authenticated;

create or replace function public.admin_members()
returns jsonb
language plpgsql
stable
security definer
set search_path = public, auth
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce((
        select jsonb_agg(to_jsonb(m) order by m.last_seen_at desc nulls last, m.created_at desc)
        from (
            select
                u.id,
                u.email,
                coalesce(nullif(btrim(p.display_name), ''), nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
                         split_part(u.email, '@', 1)) as name,
                coalesce(nullif(btrim(p.avatar_url), ''), u.raw_user_meta_data ->> 'avatar_url',
                         u.raw_user_meta_data ->> 'picture') as avatar,
                coalesce(p.role, '') as role,
                coalesce(up.plan, 'pro') as plan,
                coalesce(up.source, case when up.plan is null then 'beta' end) as plan_source,
                coalesce(u.raw_app_meta_data ->> 'provider', 'email') as sign_in,
                u.created_at,
                u.last_sign_in_at,
                a.last_seen_at,
                coalesce(a.visits, 0) as visits,
                coalesce(a.active_days, 0) as active_days,
                coalesce(a.seconds, 0) as seconds,
                (select count(*) from public.analysis_configs c where c.owner_id = u.id and c.kind = 'set') as sets,
                (select count(*) from public.prism_scans s where s.owner_id = u.id) as scans,
                (select count(*) from public.funnels f where f.owner_id = u.id) as funnels,
                (select count(*) from public.chat_messages c where c.user_id = u.id) as chat_messages,
                (select count(*) from public.sentiment_comments c where c.user_id = u.id) as comments,
                (select count(*) from public.feedback_notes n where n.user_id = u.id) as feedback,
                (select coalesce(jsonb_agg(jsonb_build_object(
                     'model', g.model, 'calls', g.calls, 'calls_30d', g.calls_30d, 'input', g.input_tokens,
                     'output', g.output_tokens, 'cache_read', g.cache_read, 'cache_write', g.cache_write,
                     'input_30d', g.input_30d, 'output_30d', g.output_30d, 'cache_read_30d', g.cache_read_30d,
                     'cache_write_30d', g.cache_write_30d, 'last_day', g.last_day)), '[]'::jsonb)
                 from (select z.model, sum(z.calls) as calls, sum(z.input_tokens) as input_tokens,
                              sum(z.output_tokens) as output_tokens, sum(z.cache_read_tokens) as cache_read,
                              sum(z.cache_write_tokens) as cache_write, max(z.day) as last_day,
                              sum(z.calls) filter (where z.day > current_date - 30) as calls_30d,
                              sum(z.input_tokens) filter (where z.day > current_date - 30) as input_30d,
                              sum(z.output_tokens) filter (where z.day > current_date - 30) as output_30d,
                              sum(z.cache_read_tokens) filter (where z.day > current_date - 30) as cache_read_30d,
                              sum(z.cache_write_tokens) filter (where z.day > current_date - 30) as cache_write_30d
                       from public.ai_usage z where z.user_id = u.id group by z.model) g) as ai
            from auth.users u
            left join public.profiles p on p.user_id = u.id
            left join public.user_plans up on up.user_id = u.id
            left join public.user_activity a on a.user_id = u.id
        ) m
    ), '[]'::jsonb);
end;
$$;

revoke all on function public.admin_members() from public, anon;
grant execute on function public.admin_members() to authenticated;

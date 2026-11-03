-- Sentiment history: keep every observation with its model, coverage and articles.
-- Safe to run more than once. Adds columns and one table; deletes nothing.
-- (The same statements are in supabase_rls.sql.)

-- One row per sentiment update. The live tables keep only the latest score.
-- subject_key is crypto, stock, or an asset key such as Crypto|sui.
-- Every observation is kept (no clean-up), with the model that scored it, how much independent news it
-- rested on (coverage: ok / thin, events, sources) and the ids and scores of its articles. Each article
-- is stored once in sentiment_articles, so a story seen again is recognised by its id.
create table if not exists public.sentiment_history (
    subject_key text not null,
    score numeric not null,
    recorded_at timestamptz not null,
    primary key (subject_key, recorded_at)
);

alter table public.sentiment_history enable row level security;

drop policy if exists "signed-in users read sentiment history" on public.sentiment_history;
create policy "signed-in users read sentiment history" on public.sentiment_history
    for select
    to authenticated
    using (true);

grant select on public.sentiment_history to authenticated;

alter table public.sentiment_history add column if not exists model text;
alter table public.sentiment_history add column if not exists coverage text;
alter table public.sentiment_history add column if not exists events integer;
alter table public.sentiment_history add column if not exists sources integer;
alter table public.sentiment_history add column if not exists article_ids text[];
alter table public.sentiment_history add column if not exists article_scores numeric[];

create table if not exists public.sentiment_articles (
    id text primary key,
    subject_key text not null,
    title text not null,
    source text,
    link text,
    published_at timestamptz,
    score numeric,
    note text,
    model text,
    first_seen timestamptz not null default now()
);

alter table public.sentiment_articles enable row level security;

drop policy if exists "signed-in users read sentiment articles" on public.sentiment_articles;
create policy "signed-in users read sentiment articles" on public.sentiment_articles
    for select
    to authenticated
    using (true);

grant select on public.sentiment_articles to authenticated;

-- The older three-argument version is replaced by one with optional extras (same name, same first
-- three arguments, so existing callers keep working).
drop function if exists public.record_sentiment_score(text, numeric, timestamptz);

-- A signed-in session may only record a score that is already the stored one for
-- that subject, with the same timestamp. The app saves the score first and records
-- it straight after, so honest calls pass and invented history does not.
-- The service role (the alert worker) and the SQL editor are not checked.
-- Parameters keep their names because the app calls this with named arguments.
-- Columns are qualified so the names cannot be read as the parameters.
create or replace function public.record_sentiment_score(
    subject_key text,
    score numeric,
    recorded_at timestamptz,
    model text default null,
    coverage text default null,
    events integer default null,
    sources integer default null,
    articles jsonb default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    stored_score numeric;
    stored_at timestamptz;
    stored_report jsonb;
    used jsonb;
    clean_key text;
begin
    if record_sentiment_score.subject_key is null
       or btrim(record_sentiment_score.subject_key) = ''
       or record_sentiment_score.score is null
       or record_sentiment_score.recorded_at is null then
        return;
    end if;
    if record_sentiment_score.score < 0 or record_sentiment_score.score > 100 then
        return;
    end if;
    if record_sentiment_score.recorded_at > now() + interval '5 minutes'
       or record_sentiment_score.recorded_at < now() - interval '30 days' then
        return;
    end if;
    clean_key := left(btrim(record_sentiment_score.subject_key), 200);
    used := record_sentiment_score.articles;

    if auth.uid() is not null then
        if record_sentiment_score.subject_key in ('crypto', 'stock') then
            select m.sentiment_score, m.sentiment_updated_at, m.sentiment_report
            into stored_score, stored_at, stored_report
            from public.market_mood as m
            where m.market_key = record_sentiment_score.subject_key;
        else
            select a.sentiment_score, a.sentiment_updated_at, a.sentiment_report
            into stored_score, stored_at, stored_report
            from public.asset_market as a
            where a.asset_key = record_sentiment_score.subject_key;
        end if;
        if stored_score is null
           or stored_at is null
           or abs(stored_score - record_sentiment_score.score) > 0.0001
           or abs(extract(epoch from (stored_at - record_sentiment_score.recorded_at))) > 1 then
            return;
        end if;
        -- A signed-in session records the articles of the stored report, never its own list.
        used := stored_report -> 'headlines';
    end if;
    if used is null or jsonb_typeof(used) <> 'array' then
        used := '[]'::jsonb;
    end if;

    insert into public.sentiment_history as h
        (subject_key, score, recorded_at, model, coverage, events, sources, article_ids, article_scores)
    select
        clean_key,
        record_sentiment_score.score,
        record_sentiment_score.recorded_at,
        left(record_sentiment_score.model, 60),
        left(record_sentiment_score.coverage, 10),
        record_sentiment_score.events,
        record_sentiment_score.sources,
        (select array_agg(left(a ->> 'id', 32) order by o)
           from jsonb_array_elements(used) with ordinality as t(a, o)
          where o <= 30 and jsonb_typeof(a) = 'object' and coalesce(a ->> 'id', '') <> ''),
        (select array_agg(case when (a ->> 'score') ~ '^[0-9]+(\.[0-9]+)?$' then (a ->> 'score')::numeric end order by o)
           from jsonb_array_elements(used) with ordinality as t(a, o)
          where o <= 30 and jsonb_typeof(a) = 'object' and coalesce(a ->> 'id', '') <> '')
    on conflict on constraint sentiment_history_pkey do nothing;

    insert into public.sentiment_articles (id, subject_key, title, source, link, published_at, score, note, model)
    select
        left(a ->> 'id', 32),
        clean_key,
        left(a ->> 'title', 400),
        left(a ->> 'source', 120),
        left(a ->> 'link', 1000),
        case when (a ->> 'published_at') ~ '^\d{4}-\d{2}-\d{2}T' then (a ->> 'published_at')::timestamptz end,
        case when (a ->> 'score') ~ '^[0-9]+(\.[0-9]+)?$' then (a ->> 'score')::numeric end,
        left(a ->> 'note', 300),
        left(record_sentiment_score.model, 60)
    from jsonb_array_elements(used) with ordinality as t(a, o)
    where o <= 30 and jsonb_typeof(a) = 'object'
      and coalesce(a ->> 'id', '') <> '' and coalesce(a ->> 'title', '') <> ''
    on conflict (id) do nothing;
end;
$$;

revoke all on function public.record_sentiment_score(text, numeric, timestamptz, text, text, integer, integer, jsonb) from public;
revoke all on function public.record_sentiment_score(text, numeric, timestamptz, text, text, integer, integer, jsonb) from anon;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz, text, text, integer, integer, jsonb) to authenticated;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz, text, text, integer, integer, jsonb) to service_role;

-- Row-level security for the Streamlit app.
-- Run this in the Supabase SQL editor. It does not delete rows.
-- The service-role key used by the alert worker bypasses these policies.
-- Re-running is safe: policies are dropped and recreated.

create table if not exists public.user_preferences (
    user_id uuid primary key references auth.users (id) on delete cascade,
    crypto_watchlist jsonb,
    stock_watchlist jsonb,
    scoring_weights jsonb,
    weight_profiles jsonb,
    settings jsonb
);

create table if not exists public.alert_preferences (
    user_id uuid primary key references auth.users (id) on delete cascade,
    enabled boolean default true,
    min_score_alert numeric default 70,
    max_score_alert numeric default 30
);

create table if not exists public.user_notifications (
    id bigint generated always as identity primary key,
    user_id uuid references auth.users (id) on delete cascade,
    asset_symbol text,
    asset_name text,
    alert_type text,
    message text,
    is_read boolean default false,
    created_at timestamptz default now(),
    emailed_at timestamptz
);

alter table public.user_notifications
    add column if not exists emailed_at timestamptz;

alter table public.user_preferences enable row level security;
alter table public.alert_preferences enable row level security;
alter table public.user_notifications enable row level security;

drop policy if exists "own preferences" on public.user_preferences;
create policy "own preferences" on public.user_preferences
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "own alert preferences" on public.alert_preferences;
create policy "own alert preferences" on public.alert_preferences
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "own notifications" on public.user_notifications;
create policy "own notifications" on public.user_notifications
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.user_preferences to authenticated;
grant select, insert, update, delete on public.alert_preferences to authenticated;
grant select, insert, update, delete on public.user_notifications to authenticated;
grant usage, select on all sequences in schema public to authenticated;

-- Public profile fields for the signed-in account, ready for later social features.
-- Anyone signed in can read profiles. Only the owner can change their own row.
create table if not exists public.profiles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    display_name text,
    bio text,
    avatar_url text,
    updated_at timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles are visible to signed-in users" on public.profiles;
create policy "profiles are visible to signed-in users" on public.profiles
    for select
    to authenticated
    using (true);

drop policy if exists "users insert own profile" on public.profiles;
create policy "users insert own profile" on public.profiles
    for insert
    to authenticated
    with check (auth.uid() = user_id);

drop policy if exists "users update own profile" on public.profiles;
create policy "users update own profile" on public.profiles
    for update
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update on public.profiles to authenticated;

-- One row per asset, shared by every signed-in account.
-- Closes feed the Trend line. The sentiment columns are the headline score.
-- The alert worker writes closes with the service-role key. A signed-in
-- session can read the row and can save a new score after Grok runs.
create table if not exists public.asset_market (
    asset_key text primary key,
    kind text not null,
    asset_id text not null,
    closes jsonb,
    closes_updated_at timestamptz,
    sentiment_score numeric,
    sentiment_report jsonb,
    sentiment_updated_at timestamptz,
    logo_url text
);

alter table public.asset_market
    add column if not exists logo_url text;

alter table public.asset_market enable row level security;

drop policy if exists "signed-in users read shared market data" on public.asset_market;
create policy "signed-in users read shared market data" on public.asset_market
    for select
    to authenticated
    using (true);

drop policy if exists "signed-in users add shared market data" on public.asset_market;
create policy "signed-in users add shared market data" on public.asset_market
    for insert
    to authenticated
    with check (true);

drop policy if exists "signed-in users update shared market data" on public.asset_market;
create policy "signed-in users update shared market data" on public.asset_market
    for update
    to authenticated
    using (true)
    with check (true);

grant select, insert, update on public.asset_market to authenticated;

-- How many accounts hold each asset. Returns counts only, never account names.
-- security definer reads every watchlist; signed-in users cannot do that directly.
create or replace function public.asset_holder_counts()
returns table (asset_key text, holders integer)
language sql
stable
security definer
set search_path = public
as $$
    select 'Crypto|' || lower(item.key), count(distinct prefs.user_id)::integer
    from public.user_preferences as prefs
    cross join lateral jsonb_each(prefs.crypto_watchlist) as item(key, value)
    where jsonb_typeof(prefs.crypto_watchlist) = 'object'
    group by lower(item.key)
    union all
    select 'Stock|' || upper(item.key), count(distinct prefs.user_id)::integer
    from public.user_preferences as prefs
    cross join lateral jsonb_each(prefs.stock_watchlist) as item(key, value)
    where jsonb_typeof(prefs.stock_watchlist) = 'object'
    group by upper(item.key);
$$;

revoke all on function public.asset_holder_counts() from public;
revoke all on function public.asset_holder_counts() from anon;
grant execute on function public.asset_holder_counts() to authenticated;

-- One take per account per asset. sentiment_at is the score it belongs to.
-- A refresh writes a new sentiment time, so older thumbs no longer count.
create table if not exists public.sentiment_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    asset_key text not null,
    sentiment_at timestamptz not null,
    vote smallint not null check (vote in (1, -1)),
    alt_score smallint check (alt_score is null or alt_score between 0 and 100),
    primary key (user_id, asset_key)
);

alter table public.sentiment_votes
    add column if not exists alt_score smallint check (alt_score is null or alt_score between 0 and 100);

alter table public.sentiment_votes enable row level security;

drop policy if exists "own sentiment votes" on public.sentiment_votes;
create policy "own sentiment votes" on public.sentiment_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.sentiment_votes to authenticated;

-- Counts for the current sentiment only. my_vote is the caller's thumb, or null.
-- alt_avg and alt_spread cover only the scores typed by people who disagree.
drop function if exists public.sentiment_crowd(text[]);
create function public.sentiment_crowd(asset_keys text[])
returns table (
    asset_key text,
    thumbs_up integer,
    thumbs_down integer,
    my_vote smallint,
    alt_count integer,
    alt_avg numeric,
    alt_spread numeric,
    my_alt smallint
)
language sql
stable
security definer
set search_path = public
as $$
    select
        market.asset_key,
        (
            select count(*)::integer
            from public.sentiment_votes as votes
            where votes.asset_key = market.asset_key
              and votes.sentiment_at = market.sentiment_updated_at
              and votes.vote = 1
        ),
        (
            select count(*)::integer
            from public.sentiment_votes as votes
            where votes.asset_key = market.asset_key
              and votes.sentiment_at = market.sentiment_updated_at
              and votes.vote = -1
        ),
        (
            select mine.vote
            from public.sentiment_votes as mine
            where mine.asset_key = market.asset_key
              and mine.user_id = auth.uid()
              and mine.sentiment_at = market.sentiment_updated_at
        ),
        (
            select count(*)::integer
            from public.sentiment_votes as votes
            where votes.asset_key = market.asset_key
              and votes.sentiment_at = market.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select round(avg(votes.alt_score), 1)
            from public.sentiment_votes as votes
            where votes.asset_key = market.asset_key
              and votes.sentiment_at = market.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select round(stddev_samp(votes.alt_score), 1)
            from public.sentiment_votes as votes
            where votes.asset_key = market.asset_key
              and votes.sentiment_at = market.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select mine.alt_score
            from public.sentiment_votes as mine
            where mine.asset_key = market.asset_key
              and mine.user_id = auth.uid()
              and mine.sentiment_at = market.sentiment_updated_at
        )
    from public.asset_market as market
    where market.asset_key = any(asset_keys)
      and market.sentiment_updated_at is not null;
$$;

revoke all on function public.sentiment_crowd(text[]) from public;
revoke all on function public.sentiment_crowd(text[]) from anon;
grant execute on function public.sentiment_crowd(text[]) to authenticated;

insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do update set public = true;

drop policy if exists "public read avatars" on storage.objects;
create policy "public read avatars" on storage.objects
    for select
    using (bucket_id = 'avatars');

drop policy if exists "users upload own avatar" on storage.objects;
create policy "users upload own avatar" on storage.objects
    for insert
    to authenticated
    with check (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

drop policy if exists "users update own avatar" on storage.objects;
create policy "users update own avatar" on storage.objects
    for update
    to authenticated
    using (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    )
    with check (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- Notes from signed-in accounts. The app always writes status submitted.
-- A person can read their own notes. Status changes happen later in the table editor.
create table if not exists public.feedback_notes (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    user_email text not null,
    kind text not null check (kind in ('issue', 'enhancement')),
    body text not null check (char_length(btrim(body)) between 1 and 4000),
    status text not null default 'submitted',
    created_at timestamptz not null default now()
);

alter table public.feedback_notes enable row level security;

drop policy if exists "insert own feedback" on public.feedback_notes;
create policy "insert own feedback" on public.feedback_notes
    for insert
    to authenticated
    with check (auth.uid() = user_id and status = 'submitted');

drop policy if exists "read own feedback" on public.feedback_notes;
create policy "read own feedback" on public.feedback_notes
    for select
    to authenticated
    using (auth.uid() = user_id);

grant select, insert on public.feedback_notes to authenticated;
grant usage, select on sequence public.feedback_notes_id_seq to authenticated;

-- One short comment per account per asset.
-- It keeps the sentiment it was answering, and lasts 12 hours from created_at.
-- A newer sentiment score does not delete it.
create table if not exists public.sentiment_comments (
    user_id uuid not null references auth.users (id) on delete cascade,
    asset_key text not null,
    sentiment_at timestamptz not null,
    body text not null check (char_length(btrim(body)) between 1 and 160),
    created_at timestamptz not null default now(),
    responded_score numeric,
    responded_summary text,
    primary key (user_id, asset_key)
);

alter table public.sentiment_comments
    add column if not exists responded_score numeric;

alter table public.sentiment_comments
    add column if not exists responded_summary text;

create index if not exists sentiment_comments_asset_idx
    on public.sentiment_comments (asset_key);

create index if not exists sentiment_comments_created_idx
    on public.sentiment_comments (created_at);

alter table public.sentiment_comments enable row level security;

drop policy if exists "read sentiment comments" on public.sentiment_comments;
create policy "read sentiment comments" on public.sentiment_comments
    for select
    to authenticated
    using (true);

drop policy if exists "insert own sentiment comment" on public.sentiment_comments;
create policy "insert own sentiment comment" on public.sentiment_comments
    for insert
    to authenticated
    with check (auth.uid() = user_id);

drop policy if exists "update own sentiment comment" on public.sentiment_comments;
create policy "update own sentiment comment" on public.sentiment_comments
    for update
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "delete own sentiment comment" on public.sentiment_comments;
create policy "delete own sentiment comment" on public.sentiment_comments
    for delete
    to authenticated
    using (auth.uid() = user_id);

grant select, insert, update, delete on public.sentiment_comments to authenticated;

-- Comments from the last 12 hours, newest first, with the sentiment they answered.
drop function if exists public.sentiment_comments(text[]);
create function public.sentiment_comments(asset_keys text[])
returns table (
    asset_key text,
    author_name text,
    avatar_url text,
    body text,
    created_at timestamptz,
    mine boolean,
    responded_score numeric,
    responded_summary text
)
language sql
stable
security definer
set search_path = public
as $$
    select
        comments.asset_key,
        coalesce(
            nullif(btrim(profiles.display_name), ''),
            nullif(split_part(users.email, '@', 1), ''),
            'Member'
        ),
        profiles.avatar_url,
        comments.body,
        comments.created_at,
        comments.user_id = auth.uid(),
        comments.responded_score,
        comments.responded_summary
    from public.sentiment_comments as comments
    left join public.profiles as profiles
      on profiles.user_id = comments.user_id
    left join auth.users as users
      on users.id = comments.user_id
    where comments.asset_key = any(asset_keys)
      and comments.created_at > now() - interval '12 hours'
    order by comments.created_at desc;
$$;

revoke all on function public.sentiment_comments(text[]) from public;
revoke all on function public.sentiment_comments(text[]) from anon;
grant execute on function public.sentiment_comments(text[]) to authenticated;

-- Removes comments older than 12 hours. A new sentiment score does not do this.
drop function if exists public.drop_sentiment_comments(text);
drop function if exists public.drop_expired_sentiment_comments();
create function public.drop_expired_sentiment_comments()
returns void
language sql
security definer
set search_path = public
as $$
    delete from public.sentiment_comments
    where created_at < now() - interval '12 hours';
$$;

revoke all on function public.drop_expired_sentiment_comments() from public;
revoke all on function public.drop_expired_sentiment_comments() from anon;
grant execute on function public.drop_expired_sentiment_comments() to authenticated;

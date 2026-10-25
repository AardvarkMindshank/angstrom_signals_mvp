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
-- Closes feed the Trend line. prices is the daily history behind charts and
-- technical scores. The sentiment columns are the headline score.
-- The alert worker writes prices with the service-role key. A signed-in
-- session writes the first row when that asset is not stored yet.
create table if not exists public.asset_market (
    asset_key text primary key,
    kind text not null,
    asset_id text not null,
    closes jsonb,
    closes_updated_at timestamptz,
    sentiment_score numeric,
    sentiment_report jsonb,
    sentiment_updated_at timestamptz,
    logo_url text,
    prices jsonb,
    prices_updated_at timestamptz
);

alter table public.asset_market
    add column if not exists logo_url text;

alter table public.asset_market
    add column if not exists prices jsonb;

alter table public.asset_market
    add column if not exists prices_updated_at timestamptz;

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
    where (
        cardinality(asset_keys) = 0
        or comments.asset_key = any(asset_keys)
      )
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

-- One shared score for the crypto market and one for the stock market.
-- These are not assets. A later agree or disagree uses market_mood_votes.
create table if not exists public.market_mood (
    market_key text primary key check (market_key in ('crypto', 'stock')),
    query text not null,
    sentiment_score numeric,
    sentiment_report jsonb,
    sentiment_updated_at timestamptz
);

alter table public.market_mood enable row level security;

drop policy if exists "signed-in users read market mood" on public.market_mood;
create policy "signed-in users read market mood" on public.market_mood
    for select
    to authenticated
    using (true);

drop policy if exists "signed-in users add market mood" on public.market_mood;
create policy "signed-in users add market mood" on public.market_mood
    for insert
    to authenticated
    with check (market_key in ('crypto', 'stock'));

drop policy if exists "signed-in users update market mood" on public.market_mood;
create policy "signed-in users update market mood" on public.market_mood
    for update
    to authenticated
    using (true)
    with check (market_key in ('crypto', 'stock'));

grant select, insert, update on public.market_mood to authenticated;

-- One take per account per market. sentiment_at is the mood it belongs to.
create table if not exists public.market_mood_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    market_key text not null check (market_key in ('crypto', 'stock')),
    sentiment_at timestamptz not null,
    vote smallint not null check (vote in (1, -1)),
    alt_score smallint check (alt_score is null or alt_score between 0 and 100),
    primary key (user_id, market_key)
);

alter table public.market_mood_votes enable row level security;

drop policy if exists "own market mood votes" on public.market_mood_votes;
create policy "own market mood votes" on public.market_mood_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id and market_key in ('crypto', 'stock'));

grant select, insert, update, delete on public.market_mood_votes to authenticated;

-- Counts for the current mood only. Prepared now so voting does not need new SQL.
drop function if exists public.market_mood_crowd(text[]);
create function public.market_mood_crowd(market_keys text[])
returns table (
    market_key text,
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
        mood.market_key,
        (
            select count(*)::integer
            from public.market_mood_votes as votes
            where votes.market_key = mood.market_key
              and votes.sentiment_at = mood.sentiment_updated_at
              and votes.vote = 1
        ),
        (
            select count(*)::integer
            from public.market_mood_votes as votes
            where votes.market_key = mood.market_key
              and votes.sentiment_at = mood.sentiment_updated_at
              and votes.vote = -1
        ),
        (
            select mine.vote
            from public.market_mood_votes as mine
            where mine.market_key = mood.market_key
              and mine.user_id = auth.uid()
              and mine.sentiment_at = mood.sentiment_updated_at
        ),
        (
            select count(*)::integer
            from public.market_mood_votes as votes
            where votes.market_key = mood.market_key
              and votes.sentiment_at = mood.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select round(avg(votes.alt_score), 1)
            from public.market_mood_votes as votes
            where votes.market_key = mood.market_key
              and votes.sentiment_at = mood.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select round(stddev_samp(votes.alt_score), 1)
            from public.market_mood_votes as votes
            where votes.market_key = mood.market_key
              and votes.sentiment_at = mood.sentiment_updated_at
              and votes.vote = -1
              and votes.alt_score is not null
        ),
        (
            select mine.alt_score
            from public.market_mood_votes as mine
            where mine.market_key = mood.market_key
              and mine.user_id = auth.uid()
              and mine.sentiment_at = mood.sentiment_updated_at
        )
    from public.market_mood as mood
    where cardinality(market_keys) = 0
       or mood.market_key = any(market_keys);
$$;

revoke all on function public.market_mood_crowd(text[]) from public;
revoke all on function public.market_mood_crowd(text[]) from anon;
grant execute on function public.market_mood_crowd(text[]) to authenticated;

-- General chat in the social panel. A reply points at a top-level comment.
-- These notes are not tied to an asset and do not expire with a sentiment score.
create table if not exists public.chat_messages (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    parent_id bigint references public.chat_messages (id) on delete cascade,
    body text not null check (char_length(btrim(body)) between 1 and 160),
    created_at timestamptz not null default now()
);

create index if not exists chat_messages_parent_idx
    on public.chat_messages (parent_id, created_at);

create index if not exists chat_messages_created_idx
    on public.chat_messages (created_at desc);

alter table public.chat_messages enable row level security;

drop policy if exists "read chat messages" on public.chat_messages;
create policy "read chat messages" on public.chat_messages
    for select
    to authenticated
    using (true);

drop policy if exists "insert own chat message" on public.chat_messages;
create policy "insert own chat message" on public.chat_messages
    for insert
    to authenticated
    with check (auth.uid() = user_id);

drop policy if exists "delete own chat message" on public.chat_messages;
create policy "delete own chat message" on public.chat_messages
    for delete
    to authenticated
    using (auth.uid() = user_id);

grant select, insert, delete on public.chat_messages to authenticated;
grant usage, select on sequence public.chat_messages_id_seq to authenticated;

create or replace function public.chat_message_parent()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if new.parent_id is not null then
        if not exists (
            select 1
            from public.chat_messages
            where id = new.parent_id
              and parent_id is null
        ) then
            raise exception 'Reply to a top-level comment only';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists chat_message_parent on public.chat_messages;
create trigger chat_message_parent
    before insert or update on public.chat_messages
    for each row
    execute function public.chat_message_parent();

-- One thumb per account per comment. Pressing the same thumb again clears it.
create table if not exists public.chat_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    message_id bigint not null references public.chat_messages (id) on delete cascade,
    vote smallint not null check (vote in (1, -1)),
    primary key (user_id, message_id)
);

alter table public.chat_votes enable row level security;

drop policy if exists "own chat votes" on public.chat_votes;
create policy "own chat votes" on public.chat_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.chat_votes to authenticated;

-- The newest threads, with their replies and thumb counts.
drop function if exists public.chat_feed();
create function public.chat_feed()
returns table (
    id bigint,
    parent_id bigint,
    author_name text,
    avatar_url text,
    body text,
    created_at timestamptz,
    mine boolean,
    thumbs_up integer,
    thumbs_down integer,
    my_vote smallint,
    author_id uuid
)
language sql
stable
security definer
set search_path = public
as $$
    with roots as (
        select chat_messages.id
        from public.chat_messages
        where chat_messages.parent_id is null
        order by chat_messages.created_at desc
        limit 60
    )
    select
        messages.id,
        messages.parent_id,
        coalesce(
            nullif(btrim(profiles.display_name), ''),
            nullif(split_part(users.email, '@', 1), ''),
            'Member'
        ),
        profiles.avatar_url,
        messages.body,
        messages.created_at,
        messages.user_id = auth.uid(),
        (
            select count(*)::integer
            from public.chat_votes as votes
            where votes.message_id = messages.id
              and votes.vote = 1
        ),
        (
            select count(*)::integer
            from public.chat_votes as votes
            where votes.message_id = messages.id
              and votes.vote = -1
        ),
        (
            select votes.vote
            from public.chat_votes as votes
            where votes.message_id = messages.id
              and votes.user_id = auth.uid()
        ),
        messages.user_id
    from public.chat_messages as messages
    left join public.profiles as profiles
      on profiles.user_id = messages.user_id
    left join auth.users as users
      on users.id = messages.user_id
    where messages.id in (select roots.id from roots)
       or messages.parent_id in (select roots.id from roots);
$$;

revoke all on function public.chat_feed() from public;
revoke all on function public.chat_feed() from anon;
grant execute on function public.chat_feed() to authenticated;

-- A stable id so a signal comment can be marked or replied to.
alter table public.sentiment_comments
    add column if not exists id bigint generated by default as identity;

create unique index if not exists sentiment_comments_id_key
    on public.sentiment_comments (id);

-- Replies belong to one signal comment and leave with it.
create table if not exists public.sentiment_replies (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    comment_id bigint not null references public.sentiment_comments (id) on delete cascade,
    body text not null check (char_length(btrim(body)) between 1 and 160),
    created_at timestamptz not null default now()
);

create index if not exists sentiment_replies_comment_idx
    on public.sentiment_replies (comment_id, created_at);

alter table public.sentiment_replies enable row level security;

drop policy if exists "read sentiment replies" on public.sentiment_replies;
create policy "read sentiment replies" on public.sentiment_replies
    for select
    to authenticated
    using (true);

drop policy if exists "insert own sentiment reply" on public.sentiment_replies;
create policy "insert own sentiment reply" on public.sentiment_replies
    for insert
    to authenticated
    with check (auth.uid() = user_id);

grant select, insert on public.sentiment_replies to authenticated;
grant usage, select on sequence public.sentiment_replies_id_seq to authenticated;

create table if not exists public.sentiment_comment_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    comment_id bigint not null references public.sentiment_comments (id) on delete cascade,
    vote smallint not null check (vote in (1, -1)),
    primary key (user_id, comment_id)
);

alter table public.sentiment_comment_votes enable row level security;

drop policy if exists "own sentiment comment votes" on public.sentiment_comment_votes;
create policy "own sentiment comment votes" on public.sentiment_comment_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.sentiment_comment_votes to authenticated;

create table if not exists public.sentiment_reply_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    reply_id bigint not null references public.sentiment_replies (id) on delete cascade,
    vote smallint not null check (vote in (1, -1)),
    primary key (user_id, reply_id)
);

alter table public.sentiment_reply_votes enable row level security;

drop policy if exists "own sentiment reply votes" on public.sentiment_reply_votes;
create policy "own sentiment reply votes" on public.sentiment_reply_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.sentiment_reply_votes to authenticated;

-- The same comment feed, plus the id and the thumbs on that comment.
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
    responded_summary text,
    id bigint,
    thumbs_up integer,
    thumbs_down integer,
    my_vote smallint,
    author_id uuid
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
        comments.responded_summary,
        comments.id,
        (
            select count(*)::integer
            from public.sentiment_comment_votes as votes
            where votes.comment_id = comments.id
              and votes.vote = 1
        ),
        (
            select count(*)::integer
            from public.sentiment_comment_votes as votes
            where votes.comment_id = comments.id
              and votes.vote = -1
        ),
        (
            select votes.vote
            from public.sentiment_comment_votes as votes
            where votes.comment_id = comments.id
              and votes.user_id = auth.uid()
        ),
        comments.user_id
    from public.sentiment_comments as comments
    left join public.profiles as profiles
      on profiles.user_id = comments.user_id
    left join auth.users as users
      on users.id = comments.user_id
    where (
        cardinality(asset_keys) = 0
        or comments.asset_key = any(asset_keys)
      )
      and comments.created_at > now() - interval '12 hours'
    order by comments.created_at desc;
$$;

revoke all on function public.sentiment_comments(text[]) from public;
revoke all on function public.sentiment_comments(text[]) from anon;
grant execute on function public.sentiment_comments(text[]) to authenticated;

drop function if exists public.sentiment_replies();
create function public.sentiment_replies()
returns table (
    id bigint,
    comment_id bigint,
    author_name text,
    avatar_url text,
    body text,
    created_at timestamptz,
    mine boolean,
    thumbs_up integer,
    thumbs_down integer,
    my_vote smallint,
    author_id uuid
)
language sql
stable
security definer
set search_path = public
as $$
    select
        replies.id,
        replies.comment_id,
        coalesce(
            nullif(btrim(profiles.display_name), ''),
            nullif(split_part(users.email, '@', 1), ''),
            'Member'
        ),
        profiles.avatar_url,
        replies.body,
        replies.created_at,
        replies.user_id = auth.uid(),
        (
            select count(*)::integer
            from public.sentiment_reply_votes as votes
            where votes.reply_id = replies.id
              and votes.vote = 1
        ),
        (
            select count(*)::integer
            from public.sentiment_reply_votes as votes
            where votes.reply_id = replies.id
              and votes.vote = -1
        ),
        (
            select votes.vote
            from public.sentiment_reply_votes as votes
            where votes.reply_id = replies.id
              and votes.user_id = auth.uid()
        ),
        replies.user_id
    from public.sentiment_replies as replies
    join public.sentiment_comments as comments
      on comments.id = replies.comment_id
    left join public.profiles as profiles
      on profiles.user_id = replies.user_id
    left join auth.users as users
      on users.id = replies.user_id
    where comments.created_at > now() - interval '12 hours'
      and replies.created_at > now() - interval '12 hours'
    order by replies.created_at asc;
$$;

revoke all on function public.sentiment_replies() from public;
revoke all on function public.sentiment_replies() from anon;
grant execute on function public.sentiment_replies() to authenticated;

drop policy if exists "delete own sentiment reply" on public.sentiment_replies;
create policy "delete own sentiment reply" on public.sentiment_replies
    for delete
    to authenticated
    using (auth.uid() = user_id);

grant delete on public.sentiment_replies to authenticated;

-- Deletes one of your notes. A top-level note takes its replies with it.
-- Runs as the owner so another person's reply can be removed with your comment.
create or replace function public.delete_own_chat_message(target_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    owner uuid;
begin
    select user_id into owner
    from public.chat_messages
    where id = target_id;
    if owner is null or owner <> auth.uid() then
        return;
    end if;
    delete from public.chat_messages where parent_id = target_id;
    delete from public.chat_messages where id = target_id;
end;
$$;

revoke all on function public.delete_own_chat_message(bigint) from public;
revoke all on function public.delete_own_chat_message(bigint) from anon;
grant execute on function public.delete_own_chat_message(bigint) to authenticated;

create or replace function public.delete_own_signal_message(target_id bigint, target_kind text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    owner uuid;
begin
    if target_kind = 'reply' then
        select user_id into owner
        from public.sentiment_replies
        where id = target_id;
        if owner is null or owner <> auth.uid() then
            return;
        end if;
        delete from public.sentiment_replies where id = target_id;
        return;
    end if;
    select user_id into owner
    from public.sentiment_comments
    where id = target_id;
    if owner is null or owner <> auth.uid() then
        return;
    end if;
    delete from public.sentiment_replies where comment_id = target_id;
    delete from public.sentiment_comments where id = target_id;
end;
$$;

revoke all on function public.delete_own_signal_message(bigint, text) from public;
revoke all on function public.delete_own_signal_message(bigint, text) from anon;
grant execute on function public.delete_own_signal_message(bigint, text) to authenticated;

-- Supabase starts the alert worker every 5 minutes. GitHub's own schedule
-- often waits about 2 hours, so this database clock is the one that keeps
-- prices on time. The GitHub token is stored in Vault, not in this file.
-- Before this can call GitHub, run this once in the SQL editor with a real
-- token in place of the placeholder. Do not commit that token.
--   select vault.create_secret(
--     'PASTE_THE_GITHUB_TOKEN_HERE',
--     'github_actions_token',
--     'Starts the Angstrom alert worker every 5 minutes'
--   );
-- The token is a fine-grained GitHub token for AardvarkMindshank/angstrom_signals_mvp
-- with Actions set to Read and write.
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

do $$
declare
  existing bigint;
begin
  select jobid into existing from cron.job where jobname = 'angstrom-alerts';
  if existing is not null then
    perform cron.unschedule(existing);
  end if;
end $$;

select cron.schedule(
  'angstrom-alerts',
  '*/5 * * * *',
  $alerts$
  select net.http_post(
    url := 'https://api.github.com/repos/AardvarkMindshank/angstrom_signals_mvp/actions/workflows/alerts.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || coalesce((
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'github_actions_token'
        limit 1
      ), ''),
      'Accept', 'application/vnd.github+json',
      'Content-Type', 'application/json',
      'User-Agent', 'angstrom-signals',
      'X-GitHub-Api-Version', '2022-11-28'
    ),
    body := '{"ref":"main"}'::jsonb,
    timeout_milliseconds := 10000
  )
  where coalesce((
    select decrypted_secret
    from vault.decrypted_secrets
    where name = 'github_actions_token'
    limit 1
  ), '') <> '';
  $alerts$
);

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

-- Social score starts at 0. A signed-in session cannot change it.
-- claim_invite_points is the only writer, and only when someone invited joins.
alter table public.profiles
    add column if not exists social_score integer not null default 0;

create or replace function public.keep_social_score()
returns trigger
language plpgsql
as $$
begin
    if coalesce(current_setting('angstrom.credit_social', true), '') = 'on' then
        if new.social_score is null then
            new.social_score := 0;
        end if;
        return new;
    end if;
    if tg_op = 'INSERT' then
        new.social_score := 0;
    else
        new.social_score := old.social_score;
    end if;
    return new;
end;
$$;

drop trigger if exists profiles_keep_social_score on public.profiles;
create trigger profiles_keep_social_score
    before insert or update on public.profiles
    for each row
    execute function public.keep_social_score();

-- One row per inviter and email. Points are awarded once, when that person joins.
create table if not exists public.invites (
    id bigint generated always as identity primary key,
    inviter_id uuid not null references auth.users (id) on delete cascade,
    email text not null,
    created_at timestamptz not null default now(),
    joined_user_id uuid references auth.users (id) on delete set null,
    credited_at timestamptz,
    unique (inviter_id, email)
);

alter table public.invites enable row level security;

create or replace function public.prepare_invite()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    own_email text;
    recent integer;
begin
    if auth.uid() is null then
        raise exception 'Sign in to send an invite';
    end if;
    new.inviter_id := auth.uid();
    new.email := lower(btrim(coalesce(new.email, '')));
    new.credited_at := null;
    new.joined_user_id := null;
    new.created_at := now();
    if new.email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
        raise exception 'Enter a valid email address';
    end if;
    select lower(email) into own_email from auth.users where id = auth.uid();
    if new.email = own_email then
        raise exception 'Use someone else''s email address';
    end if;
    select count(*) into recent
    from public.invites
    where inviter_id = auth.uid()
      and created_at > now() - interval '1 day';
    if recent >= 20 then
        raise exception 'invite limit';
    end if;
    return new;
end;
$$;

drop trigger if exists invites_prepare on public.invites;
create trigger invites_prepare
    before insert on public.invites
    for each row
    execute function public.prepare_invite();

drop policy if exists "users read own invites" on public.invites;
create policy "users read own invites" on public.invites
    for select
    to authenticated
    using (auth.uid() = inviter_id);

drop policy if exists "users send own invites" on public.invites;
create policy "users send own invites" on public.invites
    for insert
    to authenticated
    with check (auth.uid() = inviter_id);

grant select, insert on public.invites to authenticated;

-- Award 100 social points to every person who invited this account before it existed.
-- Each of those people also gets one notification in their alert feed.
create or replace function public.claim_invite_points()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    my_email text;
    joined_at timestamptz;
    joiner_name text;
    who text;
    rec record;
    awarded integer := 0;
begin
    if me is null then
        return 0;
    end if;
    select lower(email), created_at into my_email, joined_at
    from auth.users
    where id = me;
    if coalesce(my_email, '') = '' or joined_at is null then
        return 0;
    end if;

    select nullif(btrim(display_name), '') into joiner_name
    from public.profiles
    where user_id = me;
    who := left(coalesce(joiner_name, nullif(my_email, ''), 'Someone'), 80);

    perform set_config('angstrom.credit_social', 'on', true);

    for rec in
        select id, inviter_id
        from public.invites
        where email = my_email
          and credited_at is null
          and created_at <= joined_at
          and inviter_id <> me
        for update
    loop
        insert into public.profiles (user_id, social_score)
        values (rec.inviter_id, 0)
        on conflict (user_id) do nothing;

        update public.profiles
        set social_score = social_score + 100,
            updated_at = now()
        where user_id = rec.inviter_id;

        insert into public.user_notifications (
            user_id, asset_symbol, asset_name, alert_type, message
        )
        values (
            rec.inviter_id,
            '',
            who,
            'invite_joined',
            who || ' joined from your invite. 100 was added to your social score.'
        );

        update public.invites
        set joined_user_id = me,
            credited_at = now()
        where id = rec.id;

        awarded := awarded + 1;
    end loop;

    return awarded;
end;
$$;

revoke all on function public.claim_invite_points() from public;
revoke all on function public.claim_invite_points() from anon;
grant execute on function public.claim_invite_points() to authenticated;

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
    author_id uuid,
    social_score integer
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
        messages.user_id,
        coalesce(profiles.social_score, 0)
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
    author_id uuid,
    social_score integer
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
        comments.user_id,
        coalesce(profiles.social_score, 0)
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
    author_id uuid,
    social_score integer
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
        replies.user_id,
        coalesce(profiles.social_score, 0)
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

-- The first argument of vault.create_secret is the token. The second argument
-- is the name github_actions_token. A swapped pair is accepted here so one
-- mix-up does not leave the timer skipping every run.
create or replace function public.start_alert_worker()
returns bigint
language plpgsql
security definer
set search_path = public, vault, net, extensions
as $$
declare
  token text;
begin
  select decrypted_secret into token
  from vault.decrypted_secrets
  where name = 'github_actions_token'
  limit 1;

  if coalesce(token, '') = '' then
    select name into token
    from vault.decrypted_secrets
    where decrypted_secret = 'github_actions_token'
      and name like 'github_pat_%'
    limit 1;
  end if;

  if coalesce(token, '') = '' then
    raise exception 'Vault has no GitHub token named github_actions_token';
  end if;

  return net.http_post(
    url := 'https://api.github.com/repos/AardvarkMindshank/angstrom_signals_mvp/actions/workflows/alerts.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || token,
      'Accept', 'application/vnd.github+json',
      'Content-Type', 'application/json',
      'User-Agent', 'angstrom-signals',
      'X-GitHub-Api-Version', '2022-11-28'
    ),
    body := '{"ref":"main"}'::jsonb,
    timeout_milliseconds := 10000
  );
end;
$$;

revoke all on function public.start_alert_worker() from public;
revoke all on function public.start_alert_worker() from anon;
revoke all on function public.start_alert_worker() from authenticated;

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
  $alerts$ select public.start_alert_worker(); $alerts$
);

-- A new post is 5 points. A reply is 1. Rewriting an existing note does not add more.
-- Signed-in sessions cannot call this. The insert triggers are the only callers.
create or replace function public.award_social_points(target uuid, points integer)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if target is null or points is null or points not in (1, 5) then
        return;
    end if;
    perform set_config('angstrom.credit_social', 'on', true);
    insert into public.profiles (user_id, social_score)
    values (target, points)
    on conflict (user_id) do update
    set social_score = public.profiles.social_score + excluded.social_score,
        updated_at = now();
end;
$$;

revoke all on function public.award_social_points(uuid, integer) from public;
revoke all on function public.award_social_points(uuid, integer) from anon;
revoke all on function public.award_social_points(uuid, integer) from authenticated;

create or replace function public.award_chat_points()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    perform public.award_social_points(new.user_id, case when new.parent_id is null then 5 else 1 end);
    return new;
end;
$$;

drop trigger if exists chat_messages_award_points on public.chat_messages;
create trigger chat_messages_award_points
    after insert on public.chat_messages
    for each row
    execute function public.award_chat_points();

create or replace function public.award_signal_post_points()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    perform public.award_social_points(new.user_id, 5);
    return new;
end;
$$;

drop trigger if exists sentiment_comments_award_points on public.sentiment_comments;
create trigger sentiment_comments_award_points
    after insert on public.sentiment_comments
    for each row
    execute function public.award_signal_post_points();

create or replace function public.award_signal_reply_points()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    perform public.award_social_points(new.user_id, 1);
    return new;
end;
$$;

drop trigger if exists sentiment_replies_award_points on public.sentiment_replies;
create trigger sentiment_replies_award_points
    after insert on public.sentiment_replies
    for each row
    execute function public.award_signal_reply_points();

-- Groups are a filter on people already in the stream and chat.
-- The leader invites. A member joins only by accepting. No social points.
create table if not exists public.user_groups (
    id bigint generated always as identity primary key,
    leader_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    created_at timestamptz not null default now()
);

create unique index if not exists user_groups_leader_name
    on public.user_groups (leader_id, lower(name));

create table if not exists public.group_members (
    group_id bigint not null references public.user_groups (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    joined_at timestamptz not null default now(),
    primary key (group_id, user_id)
);

create index if not exists group_members_user
    on public.group_members (user_id);

create table if not exists public.group_invites (
    id bigint generated always as identity primary key,
    group_id bigint not null references public.user_groups (id) on delete cascade,
    inviter_id uuid not null references auth.users (id) on delete cascade,
    invitee_id uuid not null references auth.users (id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '30 days'),
    unique (group_id, invitee_id)
);

create index if not exists group_invites_invitee
    on public.group_invites (invitee_id);

alter table public.user_groups enable row level security;
alter table public.group_members enable row level security;
alter table public.group_invites enable row level security;

drop policy if exists "read groups you belong to" on public.user_groups;
create policy "read groups you belong to" on public.user_groups
    for select
    to authenticated
    using (
        leader_id = auth.uid()
        or exists (
            select 1 from public.group_members as members
            where members.group_id = user_groups.id
              and members.user_id = auth.uid()
        )
    );

drop policy if exists "read members of your groups" on public.group_members;
create policy "read members of your groups" on public.group_members
    for select
    to authenticated
    using (
        user_id = auth.uid()
        or exists (
            select 1 from public.user_groups as groups
            where groups.id = group_members.group_id
              and groups.leader_id = auth.uid()
        )
        or exists (
            select 1 from public.group_members as mine
            where mine.group_id = group_members.group_id
              and mine.user_id = auth.uid()
        )
    );

drop policy if exists "read own group invites" on public.group_invites;
create policy "read own group invites" on public.group_invites
    for select
    to authenticated
    using (invitee_id = auth.uid() or inviter_id = auth.uid());

grant select on public.user_groups to authenticated;
grant select on public.group_members to authenticated;
grant select on public.group_invites to authenticated;

drop function if exists public.my_groups();
create function public.my_groups()
returns table (
    id bigint,
    name text,
    leader_id uuid,
    leader_name text,
    is_leader boolean,
    members uuid[],
    people jsonb
)
language sql
stable
security definer
set search_path = public
as $$
    select
        groups.id,
        groups.name,
        groups.leader_id,
        coalesce(
            nullif(btrim(profiles.display_name), ''),
            nullif(split_part(users.email, '@', 1), ''),
            'Member'
        ),
        groups.leader_id = auth.uid(),
        coalesce(
            (
                select array_agg(members.user_id)
                from public.group_members as members
                where members.group_id = groups.id
            ),
            '{}'::uuid[]
        ),
        coalesce(
            (
                select jsonb_agg(
                    jsonb_build_object(
                        'id', named.user_id,
                        'name', named.member_name,
                        'avatar', named.avatar_url
                    )
                    order by named.member_name
                )
                from (
                    select
                        members.user_id,
                        coalesce(
                            nullif(btrim(member_profiles.display_name), ''),
                            nullif(split_part(member_users.email, '@', 1), ''),
                            'Member'
                        ) as member_name,
                        coalesce(member_profiles.avatar_url, '') as avatar_url
                    from public.group_members as members
                    left join public.profiles as member_profiles
                      on member_profiles.user_id = members.user_id
                    left join auth.users as member_users
                      on member_users.id = members.user_id
                    where members.group_id = groups.id
                ) as named
            ),
            '[]'::jsonb
        )
    from public.user_groups as groups
    left join public.profiles as profiles
      on profiles.user_id = groups.leader_id
    left join auth.users as users
      on users.id = groups.leader_id
    where groups.leader_id = auth.uid()
       or exists (
            select 1 from public.group_members as members
            where members.group_id = groups.id
              and members.user_id = auth.uid()
       )
    order by groups.name;
$$;

revoke all on function public.my_groups() from public;
revoke all on function public.my_groups() from anon;
grant execute on function public.my_groups() to authenticated;

create or replace function public.expire_my_group_invites()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    if me is null then
        return;
    end if;
    delete from public.user_notifications as notes
    using public.group_invites as invites
    where invites.invitee_id = me
      and invites.expires_at <= now()
      and notes.user_id = me
      and notes.alert_type = 'group_invite'
      and notes.asset_symbol = 'group:' || invites.id::text;
    delete from public.group_invites
    where invitee_id = me
      and expires_at <= now();
end;
$$;

revoke all on function public.expire_my_group_invites() from public;
revoke all on function public.expire_my_group_invites() from anon;
grant execute on function public.expire_my_group_invites() to authenticated;

create or replace function public.create_group_invite(
    target uuid,
    group_name text,
    chosen_group bigint
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    gid bigint;
    gname text;
    seated integer;
    waiting integer;
    inviter_label text;
    new_invite bigint;
begin
    if me is null or target is null or target = me then
        return 'self';
    end if;
    if not exists (select 1 from auth.users where id = target) then
        return 'missing';
    end if;

    if chosen_group is not null then
        select groups.id, groups.name into gid, gname
        from public.user_groups as groups
        where groups.id = chosen_group
          and groups.leader_id = me;
        if gid is null then
            return 'missing';
        end if;
    else
        gname := left(regexp_replace(btrim(coalesce(group_name, '')), '\s+', ' ', 'g'), 40);
        if gname = '' then
            return 'name';
        end if;
        select groups.id into gid
        from public.user_groups as groups
        where groups.leader_id = me
          and lower(groups.name) = lower(gname);
        if gid is null then
            if (select count(*) from public.user_groups where leader_id = me) >= 20 then
                return 'limit';
            end if;
            insert into public.user_groups (leader_id, name)
            values (me, gname)
            returning id into gid;
            insert into public.group_members (group_id, user_id)
            values (gid, me);
        end if;
    end if;

    if exists (
        select 1 from public.group_members
        where group_id = gid and user_id = target
    ) then
        return 'member';
    end if;
    if exists (
        select 1 from public.group_invites
        where group_id = gid
          and invitee_id = target
          and expires_at > now()
    ) then
        return 'pending';
    end if;

    delete from public.user_notifications as notes
    using public.group_invites as invites
    where invites.group_id = gid
      and invites.invitee_id = target
      and notes.alert_type = 'group_invite'
      and notes.asset_symbol = 'group:' || invites.id::text;
    delete from public.group_invites
    where group_id = gid and invitee_id = target;

    select count(*) into seated from public.group_members where group_id = gid;
    select count(*) into waiting
    from public.group_invites
    where group_id = gid and expires_at > now();
    if seated + waiting >= 50 then
        return 'full';
    end if;

    insert into public.group_invites (group_id, inviter_id, invitee_id, expires_at)
    values (gid, me, target, now() + interval '30 days')
    returning id into new_invite;

    select coalesce(
        nullif(btrim(profiles.display_name), ''),
        nullif(split_part(users.email, '@', 1), ''),
        'Someone'
    ) into inviter_label
    from auth.users as users
    left join public.profiles as profiles
      on profiles.user_id = users.id
    where users.id = me;
    inviter_label := left(coalesce(inviter_label, 'Someone'), 80);

    insert into public.user_notifications (
        user_id, asset_symbol, asset_name, alert_type, message
    )
    values (
        target,
        'group:' || new_invite::text,
        gname,
        'group_invite',
        inviter_label || ' invited you to the group ' || gname || '.'
    );
    return 'ok';
exception
    when unique_violation then
        return 'pending';
end;
$$;

revoke all on function public.create_group_invite(uuid, text, bigint) from public;
revoke all on function public.create_group_invite(uuid, text, bigint) from anon;
grant execute on function public.create_group_invite(uuid, text, bigint) to authenticated;

create or replace function public.respond_group_invite(invite_id bigint, accept boolean)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    rec public.group_invites%rowtype;
    gname text;
    leader uuid;
    seated integer;
    who text;
begin
    if me is null or invite_id is null then
        return 'gone';
    end if;
    select * into rec
    from public.group_invites
    where id = invite_id
      and invitee_id = me
    for update;
    if not found then
        delete from public.user_notifications
        where user_id = me
          and alert_type = 'group_invite'
          and asset_symbol = 'group:' || invite_id::text;
        return 'gone';
    end if;
    if rec.expires_at <= now() or accept is not true then
        delete from public.user_notifications
        where user_id = me
          and alert_type = 'group_invite'
          and asset_symbol = 'group:' || rec.id::text;
        delete from public.group_invites where id = rec.id;
        if rec.expires_at <= now() then
            return 'expired';
        end if;
        return 'dismissed';
    end if;

    select groups.name, groups.leader_id into gname, leader
    from public.user_groups as groups
    where groups.id = rec.group_id;
    if leader is null then
        delete from public.user_notifications
        where user_id = me
          and alert_type = 'group_invite'
          and asset_symbol = 'group:' || rec.id::text;
        delete from public.group_invites where id = rec.id;
        return 'gone';
    end if;
    select count(*) into seated
    from public.group_members
    where group_id = rec.group_id;
    if seated >= 50 then
        return 'full';
    end if;

    insert into public.group_members (group_id, user_id)
    values (rec.group_id, me)
    on conflict do nothing;

    select coalesce(
        nullif(btrim(profiles.display_name), ''),
        nullif(split_part(users.email, '@', 1), ''),
        'Someone'
    ) into who
    from auth.users as users
    left join public.profiles as profiles
      on profiles.user_id = users.id
    where users.id = me;
    who := left(coalesce(who, 'Someone'), 80);

    insert into public.user_notifications (
        user_id, asset_symbol, asset_name, alert_type, message
    )
    values (
        leader,
        '',
        gname,
        'group_joined',
        who || ' joined your group ' || gname || '.'
    );

    delete from public.user_notifications
    where user_id = me
      and alert_type = 'group_invite'
      and asset_symbol = 'group:' || rec.id::text;
    delete from public.group_invites where id = rec.id;
    return 'ok';
end;
$$;

revoke all on function public.respond_group_invite(bigint, boolean) from public;
revoke all on function public.respond_group_invite(bigint, boolean) from anon;
grant execute on function public.respond_group_invite(bigint, boolean) to authenticated;

create or replace function public.delete_my_group(chosen_group bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    if me is null or chosen_group is null then
        return;
    end if;
    if not exists (
        select 1 from public.user_groups
        where id = chosen_group and leader_id = me
    ) then
        return;
    end if;
    delete from public.user_notifications as notes
    using public.group_invites as invites
    where invites.group_id = chosen_group
      and notes.alert_type = 'group_invite'
      and notes.asset_symbol = 'group:' || invites.id::text;
    delete from public.user_groups
    where id = chosen_group
      and leader_id = me;
end;
$$;

revoke all on function public.delete_my_group(bigint) from public;
revoke all on function public.delete_my_group(bigint) from anon;
grant execute on function public.delete_my_group(bigint) to authenticated;

create or replace function public.leave_group(chosen_group bigint)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    if me is null or chosen_group is null then
        return 'missing';
    end if;
    if exists (
        select 1 from public.user_groups
        where id = chosen_group and leader_id = me
    ) then
        return 'leader';
    end if;
    delete from public.group_members
    where group_id = chosen_group
      and user_id = me;
    return 'ok';
end;
$$;

revoke all on function public.leave_group(bigint) from public;
revoke all on function public.leave_group(bigint) from anon;
grant execute on function public.leave_group(bigint) to authenticated;

create or replace function public.remove_group_member(chosen_group bigint, person uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    removed integer;
begin
    if me is null or chosen_group is null or person is null then
        return 'missing';
    end if;
    if not exists (
        select 1 from public.user_groups
        where id = chosen_group and leader_id = me
    ) then
        return 'leader';
    end if;
    if person = me then
        return 'self';
    end if;
    delete from public.group_members
    where group_id = chosen_group
      and user_id = person;
    get diagnostics removed = row_count;
    if removed = 0 then
        return 'missing';
    end if;
    return 'ok';
end;
$$;

revoke all on function public.remove_group_member(bigint, uuid) from public;
revoke all on function public.remove_group_member(bigint, uuid) from anon;
grant execute on function public.remove_group_member(bigint, uuid) to authenticated;

-- One row per sentiment update. The live tables keep only the latest score.
-- subject_key is crypto, stock, or an asset key such as Crypto|sui.
-- Rows older than 30 days are removed when a new score is recorded.
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

create or replace function public.record_sentiment_score(
    subject_key text,
    score numeric,
    recorded_at timestamptz
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if subject_key is null or btrim(subject_key) = '' or score is null or recorded_at is null then
        return;
    end if;
    if score < 0 or score > 100 then
        return;
    end if;
    insert into public.sentiment_history (subject_key, score, recorded_at)
    values (left(btrim(subject_key), 200), score, recorded_at)
    on conflict (subject_key, recorded_at) do nothing;

    delete from public.sentiment_history
    where recorded_at < now() - interval '30 days';
end;
$$;

revoke all on function public.record_sentiment_score(text, numeric, timestamptz) from public;
revoke all on function public.record_sentiment_score(text, numeric, timestamptz) from anon;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz) to authenticated;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz) to service_role;

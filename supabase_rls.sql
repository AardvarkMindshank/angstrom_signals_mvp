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

alter table public.asset_market
    add column if not exists market_cap numeric;

alter table public.asset_market
    add column if not exists market_rank integer;

alter table public.asset_market
    add column if not exists market_stats_updated_at timestamptz;

alter table public.asset_market
    add column if not exists next_earnings date;

alter table public.asset_market
    add column if not exists earnings_checked_at timestamptz;

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

-- Every signed-in account can write this table, so the policies above cannot say
-- who may change what. This trigger does. A signed-in session may:
--   * add a row for an asset nobody has stored yet,
--   * fill a group of columns that is still empty,
--   * replace a group only once its stored copy is older than 12 hours
--     (a fallback for when the worker is behind).
-- Anything else is quietly kept as stored, so a fresh shared value cannot be
-- overwritten and the app does not see an error. The shape of every write is
-- also checked, so a session cannot store oversized or out-of-range data.
-- The service role and the SQL editor have no auth.uid() and pass straight through.
create or replace function public.guard_asset_market_write()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    cutoff timestamptz := now() - interval '12 hours';
    ceiling_at constant timestamptz := now() + interval '5 minutes';
begin
    if auth.uid() is null then
        return new;
    end if;

    if new.sentiment_score is not null and (new.sentiment_score < 0 or new.sentiment_score > 100) then
        raise exception 'sentiment_score must be between 0 and 100';
    end if;
    if new.logo_url is not null and new.logo_url !~* '^https://' then
        raise exception 'logo_url must be an https address';
    end if;
    if new.market_cap is not null and new.market_cap < 0 then
        raise exception 'market_cap cannot be negative';
    end if;
    if new.market_rank is not null and (new.market_rank < 1 or new.market_rank > 1000000) then
        raise exception 'market_rank is out of range';
    end if;
    if pg_column_size(new.closes) > 262144
       or pg_column_size(new.prices) > 1048576
       or pg_column_size(new.sentiment_report) > 65536 then
        raise exception 'shared market data is too large';
    end if;
    if new.closes_updated_at > ceiling_at
       or new.sentiment_updated_at > ceiling_at
       or new.prices_updated_at > ceiling_at
       or new.market_stats_updated_at > ceiling_at
       or new.earnings_checked_at > ceiling_at then
        raise exception 'timestamps cannot be in the future';
    end if;

    if tg_op = 'INSERT' then
        return new;
    end if;

    new.asset_key := old.asset_key;
    new.kind := old.kind;
    new.asset_id := old.asset_id;

    if old.closes is not null
       and (old.closes_updated_at is null or old.closes_updated_at > cutoff
            or new.closes_updated_at is null or new.closes_updated_at <= old.closes_updated_at) then
        new.closes := old.closes;
        new.closes_updated_at := old.closes_updated_at;
    end if;

    if old.prices is not null
       and (old.prices_updated_at is null or old.prices_updated_at > cutoff
            or new.prices_updated_at is null or new.prices_updated_at <= old.prices_updated_at) then
        new.prices := old.prices;
        new.prices_updated_at := old.prices_updated_at;
    end if;

    if old.sentiment_updated_at is not null
       and (old.sentiment_updated_at > cutoff
            or new.sentiment_updated_at is null or new.sentiment_updated_at <= old.sentiment_updated_at) then
        new.sentiment_score := old.sentiment_score;
        new.sentiment_report := old.sentiment_report;
        new.sentiment_updated_at := old.sentiment_updated_at;
    end if;

    if old.logo_url is not null then
        new.logo_url := old.logo_url;
    end if;

    -- Earnings dates: kept for 6 hours, then a newer check may replace them.
    if old.earnings_checked_at is not null
       and (old.earnings_checked_at > now() - interval '6 hours'
            or new.earnings_checked_at is null or new.earnings_checked_at <= old.earnings_checked_at) then
        new.next_earnings := old.next_earnings;
        new.earnings_checked_at := old.earnings_checked_at;
    end if;

    -- Market cap and rank follow the same rule: kept for 20 minutes, then a newer reading may replace them.
    if old.market_stats_updated_at is not null
       and (old.market_stats_updated_at > now() - interval '20 minutes'
            or new.market_stats_updated_at is null or new.market_stats_updated_at <= old.market_stats_updated_at) then
        new.market_cap := old.market_cap;
        new.market_rank := old.market_rank;
        new.market_stats_updated_at := old.market_stats_updated_at;
    end if;

    return new;
end;
$$;

drop trigger if exists guard_asset_market_write on public.asset_market;
create trigger guard_asset_market_write
    before insert or update on public.asset_market
    for each row
    execute function public.guard_asset_market_write();

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

-- Same idea as guard_asset_market_write: a session may add a mood or refresh one
-- older than 12 hours. A fresh mood stays as stored. The service role passes through.
create or replace function public.guard_market_mood_write()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if auth.uid() is null then
        return new;
    end if;
    if new.sentiment_score is not null and (new.sentiment_score < 0 or new.sentiment_score > 100) then
        raise exception 'sentiment_score must be between 0 and 100';
    end if;
    if pg_column_size(new.sentiment_report) > 65536 then
        raise exception 'shared market data is too large';
    end if;
    if new.sentiment_updated_at > now() + interval '5 minutes' then
        raise exception 'timestamps cannot be in the future';
    end if;
    if tg_op = 'INSERT' then
        return new;
    end if;

    new.market_key := old.market_key;
    if old.sentiment_updated_at is not null
       and (old.sentiment_updated_at > now() - interval '12 hours'
            or new.sentiment_updated_at is null or new.sentiment_updated_at <= old.sentiment_updated_at) then
        new.query := old.query;
        new.sentiment_score := old.sentiment_score;
        new.sentiment_report := old.sentiment_report;
        new.sentiment_updated_at := old.sentiment_updated_at;
    end if;
    return new;
end;
$$;

drop trigger if exists guard_market_mood_write on public.market_mood;
create trigger guard_market_mood_write
    before insert or update on public.market_mood
    for each row
    execute function public.guard_market_mood_write();

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

-- A signed-in session may only record a score that is already the stored one for
-- that subject, with the same timestamp. The app saves the score first and records
-- it straight after, so honest calls pass and invented history does not.
-- The service role (the alert worker) and the SQL editor are not checked.
-- Parameters keep their names because the app calls this with named arguments.
-- Columns are qualified so the names cannot be read as the parameters.
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
declare
    stored_score numeric;
    stored_at timestamptz;
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

    if auth.uid() is not null then
        if record_sentiment_score.subject_key in ('crypto', 'stock') then
            select m.sentiment_score, m.sentiment_updated_at
            into stored_score, stored_at
            from public.market_mood as m
            where m.market_key = record_sentiment_score.subject_key;
        else
            select a.sentiment_score, a.sentiment_updated_at
            into stored_score, stored_at
            from public.asset_market as a
            where a.asset_key = record_sentiment_score.subject_key;
        end if;
        if stored_score is null
           or stored_at is null
           or abs(stored_score - record_sentiment_score.score) > 0.0001
           or abs(extract(epoch from (stored_at - record_sentiment_score.recorded_at))) > 1 then
            return;
        end if;
    end if;

    insert into public.sentiment_history as h (subject_key, score, recorded_at)
    values (
        left(btrim(record_sentiment_score.subject_key), 200),
        record_sentiment_score.score,
        record_sentiment_score.recorded_at
    )
    on conflict on constraint sentiment_history_pkey do nothing;

    delete from public.sentiment_history as old_rows
    where old_rows.recorded_at < now() - interval '30 days';
end;
$$;

revoke all on function public.record_sentiment_score(text, numeric, timestamptz) from public;
revoke all on function public.record_sentiment_score(text, numeric, timestamptz) from anon;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz) to authenticated;
grant execute on function public.record_sentiment_score(text, numeric, timestamptz) to service_role;

-- One long-run evidence record per asset: how the technical score lined up with
-- later price over about five years. Signed-in users can read it. Only the alert
-- worker (service role) writes it, so no account can edit what everyone is shown.
create table if not exists public.asset_evidence (
    asset_key text primary key,
    computed_at timestamptz not null default now(),
    payload jsonb not null
);

alter table public.asset_evidence enable row level security;

drop policy if exists "signed-in users read asset evidence" on public.asset_evidence;
create policy "signed-in users read asset evidence" on public.asset_evidence
    for select
    to authenticated
    using (true);

revoke all on public.asset_evidence from anon;
revoke insert, update, delete on public.asset_evidence from authenticated;
grant select on public.asset_evidence to authenticated;

-- One report per account per comment. The app emails report@angstromsignals.com as well.
-- A person can read the reports they sent. The crowd cannot.
create table if not exists public.comment_reports (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    user_email text not null,
    place text not null check (place in ('chat', 'signal')),
    message_id bigint not null,
    message_kind text not null check (message_kind in ('comment', 'reply')),
    author_id uuid,
    asset_key text not null default '',
    comment_body text not null check (char_length(btrim(comment_body)) between 1 and 160),
    reason text not null check (reason in ('promotion', 'advice', 'harassment', 'spam', 'other')),
    note text not null default '' check (char_length(note) <= 500),
    status text not null default 'reported',
    created_at timestamptz not null default now(),
    unique (user_id, place, message_id, message_kind)
);

alter table public.comment_reports enable row level security;

drop policy if exists "insert own comment report" on public.comment_reports;
create policy "insert own comment report" on public.comment_reports
    for insert
    to authenticated
    with check (auth.uid() = user_id and status = 'reported');

drop policy if exists "read own comment reports" on public.comment_reports;
create policy "read own comment reports" on public.comment_reports
    for select
    to authenticated
    using (auth.uid() = user_id);

grant select, insert on public.comment_reports to authenticated;
grant usage, select on sequence public.comment_reports_id_seq to authenticated;

-- Admin is a role on the profile. A signed-in session cannot change it.
alter table public.profiles
    add column if not exists role text not null default 'member';

alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles
    add constraint profiles_role_check check (role in ('member', 'admin'));

create or replace function public.keep_profile_role()
returns trigger
language plpgsql
as $$
begin
    if auth.uid() is null then
        return new;
    end if;
    if tg_op = 'INSERT' then
        new.role := 'member';
    else
        new.role := old.role;
    end if;
    return new;
end;
$$;

drop trigger if exists keep_profile_role on public.profiles;
create trigger keep_profile_role
    before insert or update on public.profiles
    for each row
    execute function public.keep_profile_role();

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.profiles
        where user_id = auth.uid()
          and role = 'admin'
    );
$$;

revoke all on function public.is_admin() from public;
revoke all on function public.is_admin() from anon;
grant execute on function public.is_admin() to authenticated;

-- No admin is created here. Make the first one by hand in the SQL editor, once:
--   update public.profiles set role = 'admin'
--   where user_id = (select id from auth.users where lower(email) = lower('you@example.com'));
-- The keep_profile_role trigger lets the SQL editor change roles; a signed-in session cannot.
-- An account that was already made admin by an earlier run of this file stays admin.

-- Each feedback status change is its own dated row.
alter table public.feedback_notes drop constraint if exists feedback_notes_status_check;
alter table public.feedback_notes
    add constraint feedback_notes_status_check check (
        status in (
            'submitted', 'under_review', 'accepted', 'in_development',
            'in_production', 'rejected', 'closed'
        )
    );

create table if not exists public.feedback_events (
    id bigint generated always as identity primary key,
    feedback_id bigint not null references public.feedback_notes (id) on delete cascade,
    status text not null,
    note text not null default '',
    actor_id uuid,
    created_at timestamptz not null default now()
);

alter table public.feedback_events enable row level security;
revoke all on public.feedback_events from public;
revoke all on public.feedback_events from anon;
revoke all on public.feedback_events from authenticated;

create or replace function public.admin_feedback()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce((
        select jsonb_agg(to_jsonb(item) order by item.created_at desc)
        from (
            select
                notes.id,
                notes.kind,
                notes.body,
                notes.status,
                notes.user_email as email,
                notes.created_at,
                coalesce(
                    nullif(btrim(profiles.display_name), ''),
                    nullif(split_part(notes.user_email, '@', 1), ''),
                    'Member'
                ) as username,
                coalesce(profiles.avatar_url, '') as avatar,
                coalesce((
                    select jsonb_agg(jsonb_build_object(
                        'status', events.status,
                        'note', events.note,
                        'at', events.created_at
                    ) order by events.created_at)
                    from public.feedback_events events
                    where events.feedback_id = notes.id
                ), '[]'::jsonb) as events
            from public.feedback_notes notes
            left join public.profiles profiles on profiles.user_id = notes.user_id
        ) item
    ), '[]'::jsonb);
end;
$$;

create or replace function public.review_feedback(note_id bigint, next_status text, reason text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    current_status text;
    clean_reason text;
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    select status into current_status
    from public.feedback_notes
    where id = note_id;
    if current_status is null then
        return 'missing';
    end if;
    clean_reason := left(btrim(coalesce(reason, '')), 500);
    if next_status = 'rejected' and char_length(clean_reason) < 4 then
        return 'reason';
    end if;
    if not (
        (current_status = 'submitted' and next_status = 'under_review')
        or (current_status = 'under_review' and next_status in ('accepted', 'rejected'))
        or (current_status = 'accepted' and next_status = 'in_development')
        or (current_status = 'in_development' and next_status = 'in_production')
        or (current_status = 'in_production' and next_status = 'closed')
        or (current_status = 'rejected' and next_status = 'closed')
    ) then
        return 'step';
    end if;
    update public.feedback_notes
    set status = next_status
    where id = note_id;
    insert into public.feedback_events (feedback_id, status, note, actor_id)
    values (
        note_id,
        next_status,
        case when next_status = 'rejected' then clean_reason else '' end,
        auth.uid()
    );
    return 'ok';
end;
$$;

revoke all on function public.admin_feedback() from public;
revoke all on function public.admin_feedback() from anon;
grant execute on function public.admin_feedback() to authenticated;

revoke all on function public.review_feedback(bigint, text, text) from public;
revoke all on function public.review_feedback(bigint, text, text) from anon;
grant execute on function public.review_feedback(bigint, text, text) to authenticated;

-- Reported comments move reported -> under review -> rejected or upheld.
-- A warning is one dated row, so the count is how many times that person was upheld.
alter table public.comment_reports alter column status set default 'reported';
update public.comment_reports set status = 'reported' where status = 'submitted';

alter table public.comment_reports drop constraint if exists comment_reports_status_check;
alter table public.comment_reports
    add constraint comment_reports_status_check check (
        status in ('reported', 'under_review', 'rejected', 'upheld')
    );

create table if not exists public.comment_report_events (
    id bigint generated always as identity primary key,
    report_id bigint not null references public.comment_reports (id) on delete cascade,
    status text not null,
    note text not null default '',
    actor_id uuid,
    created_at timestamptz not null default now()
);

create table if not exists public.user_warnings (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    report_id bigint references public.comment_reports (id) on delete set null,
    reason text not null,
    created_at timestamptz not null default now()
);

alter table public.comment_report_events enable row level security;
alter table public.user_warnings enable row level security;
revoke all on public.comment_report_events from public, anon, authenticated;
revoke all on public.user_warnings from public, anon, authenticated;

-- The account's own-row rule blocks a notice written for someone else.
-- An admin decision is allowed to write that notice.
drop policy if exists "admins insert notifications" on public.user_notifications;
create policy "admins insert notifications" on public.user_notifications
    for insert
    with check (public.is_admin());

create or replace function public.admin_remove_comment(place text, message_kind text, message_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        return;
    end if;
    if place = 'chat' then
        delete from public.chat_messages where id = message_id;
        return;
    end if;
    if message_kind = 'reply' then
        delete from public.sentiment_replies where id = message_id;
        return;
    end if;
    delete from public.sentiment_comments where id = message_id;
end;
$$;

revoke all on function public.admin_remove_comment(text, text, bigint) from public;
revoke all on function public.admin_remove_comment(text, text, bigint) from anon;
revoke all on function public.admin_remove_comment(text, text, bigint) from authenticated;

create or replace function public.admin_reports()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce((
        select jsonb_agg(to_jsonb(item) order by item.created_at desc)
        from (
            select
                reports.id,
                reports.place,
                reports.message_kind,
                reports.comment_body,
                reports.reason,
                reports.note,
                reports.status,
                reports.asset_key,
                reports.created_at,
                reports.user_email as reporter_email,
                coalesce(nullif(btrim(reporter.display_name), ''), reports.user_email) as reporter_name,
                coalesce(reporter.avatar_url, '') as reporter_avatar,
                coalesce(nullif(btrim(author.display_name), ''), 'Member') as author_name,
                coalesce(author.avatar_url, '') as author_avatar,
                (
                    select count(*)
                    from public.user_warnings warnings
                    where warnings.user_id = reports.author_id
                ) as warnings,
                coalesce((
                    select jsonb_agg(jsonb_build_object(
                        'status', events.status,
                        'note', events.note,
                        'at', events.created_at
                    ) order by events.created_at)
                    from public.comment_report_events events
                    where events.report_id = reports.id
                ), '[]'::jsonb) as events
            from public.comment_reports reports
            left join public.profiles reporter on reporter.user_id = reports.user_id
            left join public.profiles author on author.user_id = reports.author_id
        ) item
    ), '[]'::jsonb);
end;
$$;

create or replace function public.review_comment_report(report_id bigint, next_status text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    chosen public.comment_reports%rowtype;
    current_status text;
    reason_label text;
    warning_number integer;
    reporter_id uuid;
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    if next_status not in ('under_review', 'rejected', 'upheld') then
        return 'step';
    end if;
    select * into chosen from public.comment_reports where id = report_id;
    if not found then
        return 'missing';
    end if;
    current_status := chosen.status;
    if current_status = 'submitted' then
        current_status := 'reported';
    end if;
    if not (
        (current_status = 'reported' and next_status = 'under_review')
        or (current_status = 'under_review' and next_status in ('rejected', 'upheld'))
    ) then
        return 'step';
    end if;
    if next_status = 'upheld' then
        perform public.admin_remove_comment(chosen.place, chosen.message_kind, chosen.message_id);
        reason_label := case chosen.reason
            when 'promotion' then 'promoting an asset'
            when 'advice' then 'presenting it as financial advice'
            when 'harassment' then 'harassment or a personal attack'
            when 'spam' then 'spam'
            else 'something else'
        end;
        if chosen.author_id is not null then
            insert into public.user_warnings (user_id, report_id, reason)
            values (chosen.author_id, chosen.id, chosen.reason);
            select count(*) into warning_number
            from public.user_warnings
            where user_id = chosen.author_id;
            insert into public.user_notifications (
                user_id, asset_symbol, asset_name, alert_type, message
            )
            values (
                chosen.author_id,
                '',
                'Comment',
                'moderation_warning',
                'A comment you posted was removed because it broke the socials policy ('
                    || reason_label || '). This is warning ' || warning_number || '.'
            );
        end if;
    end if;
    update public.comment_reports
    set status = next_status
    where place = chosen.place
      and message_id = chosen.message_id
      and message_kind = chosen.message_kind
      and status in ('reported', 'submitted', 'under_review');
    insert into public.comment_report_events (report_id, status, actor_id)
    select reports.id, next_status, auth.uid()
    from public.comment_reports reports
    where reports.place = chosen.place
      and reports.message_id = chosen.message_id
      and reports.message_kind = chosen.message_kind
      and reports.status = next_status
      and not exists (
          select 1
          from public.comment_report_events events
          where events.report_id = reports.id
            and events.status = next_status
      );
    if next_status in ('rejected', 'upheld') then
        for reporter_id in
            select distinct reports.user_id
            from public.comment_reports as reports
            where reports.place = chosen.place
              and reports.message_id = chosen.message_id
              and reports.message_kind = chosen.message_kind
              and reports.user_id is distinct from chosen.author_id
        loop
            insert into public.user_notifications (
                user_id, asset_symbol, asset_name, alert_type, message
            )
            values (
                reporter_id,
                '',
                'Report',
                'report_update',
                case
                    when next_status = 'upheld' then 'Your report was upheld. The comment was removed.'
                    else 'Your report was reviewed. The comment stays.'
                end
            );
        end loop;
    end if;
    return 'ok';
end;
$$;

revoke all on function public.admin_reports() from public;
revoke all on function public.admin_reports() from anon;
grant execute on function public.admin_reports() to authenticated;

revoke all on function public.review_comment_report(bigint, text) from public;
revoke all on function public.review_comment_report(bigint, text) from anon;
grant execute on function public.review_comment_report(bigint, text) to authenticated;

-- Barred emails cannot sign in. The list itself is not readable from the app.
create table if not exists public.email_blacklist (
    email text primary key,
    created_at timestamptz not null default now(),
    created_by uuid
);

alter table public.email_blacklist enable row level security;
revoke all on public.email_blacklist from public;
revoke all on public.email_blacklist from anon;
revoke all on public.email_blacklist from authenticated;

create or replace function public.email_is_barred(address text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.email_blacklist
        where email = lower(btrim(coalesce(address, '')))
    );
$$;

create or replace function public.account_barred()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.email_blacklist
        where email = lower(coalesce(auth.jwt() ->> 'email', ''))
    );
$$;

create or replace function public.bar_blacklisted_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.email is not null and exists (
        select 1
        from public.email_blacklist
        where email = lower(new.email)
    ) then
        new.banned_until := timestamptz '2999-12-31 00:00:00+00';
    end if;
    return new;
end;
$$;

drop trigger if exists bar_blacklisted_user on auth.users;
create trigger bar_blacklisted_user
    before insert or update of email on auth.users
    for each row
    execute function public.bar_blacklisted_user();

create or replace function public._bar_auth_email(address text)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    target uuid;
begin
    for target in
        select id
        from auth.users
        where lower(coalesce(email, '')) = address
    loop
        update auth.users
        set banned_until = timestamptz '2999-12-31 00:00:00+00'
        where id = target;
        begin
            delete from auth.refresh_tokens
            where user_id::text = target::text;
        exception
            when undefined_table or insufficient_privilege or foreign_key_violation then
                null;
        end;
        begin
            delete from auth.sessions
            where user_id = target;
        exception
            when undefined_table or insufficient_privilege or foreign_key_violation then
                null;
        end;
    end loop;
end;
$$;

create or replace function public._clear_auth_bar(address text)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
begin
    update auth.users
    set banned_until = null
    where lower(coalesce(email, '')) = address;
end;
$$;

create or replace function public.admin_blacklist()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce(
        (
            select jsonb_agg(
                jsonb_build_object(
                    'email', listed.email,
                    'created_at', listed.created_at
                )
                order by listed.created_at desc
            )
            from public.email_blacklist as listed
        ),
        '[]'::jsonb
    );
end;
$$;

create or replace function public.add_blacklist_email(address text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    clean text := lower(btrim(coalesce(address, '')));
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    if clean !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
        return 'email';
    end if;
    if clean = lower(coalesce(auth.jwt() ->> 'email', '')) then
        return 'self';
    end if;
    if exists (select 1 from public.email_blacklist where email = clean) then
        return 'exists';
    end if;
    insert into public.email_blacklist (email, created_by)
    values (clean, auth.uid());
    perform public._bar_auth_email(clean);
    return 'ok';
end;
$$;

create or replace function public.remove_blacklist_email(address text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    clean text := lower(btrim(coalesce(address, '')));
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    delete from public.email_blacklist
    where email = clean;
    if not found then
        return 'missing';
    end if;
    perform public._clear_auth_bar(clean);
    return 'ok';
end;
$$;

revoke all on function public.email_is_barred(text) from public;
revoke all on function public.account_barred() from public;
revoke all on function public.bar_blacklisted_user() from public;
revoke all on function public._bar_auth_email(text) from public;
revoke all on function public._clear_auth_bar(text) from public;
revoke all on function public.admin_blacklist() from public;
revoke all on function public.add_blacklist_email(text) from public;
revoke all on function public.remove_blacklist_email(text) from public;

revoke all on function public.email_is_barred(text) from anon;
revoke all on function public.account_barred() from anon;
revoke all on function public.bar_blacklisted_user() from anon;
revoke all on function public._bar_auth_email(text) from anon;
revoke all on function public._clear_auth_bar(text) from anon;
revoke all on function public.admin_blacklist() from anon;
revoke all on function public.add_blacklist_email(text) from anon;
revoke all on function public.remove_blacklist_email(text) from anon;

revoke all on function public.email_is_barred(text) from authenticated;
revoke all on function public.account_barred() from authenticated;
revoke all on function public.bar_blacklisted_user() from authenticated;
revoke all on function public._bar_auth_email(text) from authenticated;
revoke all on function public._clear_auth_bar(text) from authenticated;
revoke all on function public.admin_blacklist() from authenticated;
revoke all on function public.add_blacklist_email(text) from authenticated;
revoke all on function public.remove_blacklist_email(text) from authenticated;

grant execute on function public.email_is_barred(text) to anon, authenticated;
grant execute on function public.account_barred() to authenticated;
grant execute on function public.admin_blacklist() to authenticated;
grant execute on function public.add_blacklist_email(text) to authenticated;
grant execute on function public.remove_blacklist_email(text) to authenticated;


-- ------------------------------------------------------------------
-- Closed beta. New accounts are only allowed for approved emails.
-- Accounts that already exist are not touched.
-- ------------------------------------------------------------------

create table if not exists public.beta_settings (
    id boolean primary key default true check (id),
    signup_open boolean not null default false
);
insert into public.beta_settings (id, signup_open) values (true, false)
on conflict (id) do nothing;

alter table public.beta_settings enable row level security;
revoke all on public.beta_settings from public;
revoke all on public.beta_settings from anon;
revoke all on public.beta_settings from authenticated;

create table if not exists public.beta_access (
    email text primary key,
    created_at timestamptz not null default now(),
    created_by uuid,
    request_id bigint
);

alter table public.beta_access enable row level security;
revoke all on public.beta_access from public;
revoke all on public.beta_access from anon;
revoke all on public.beta_access from authenticated;

-- Requests from the website form. The website may add a row (nothing more), and nobody can read them
-- except through the admin functions below.
create table if not exists public.beta_requests (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    name text not null check (char_length(name) between 1 and 100),
    email text not null check (char_length(email) between 3 and 150),
    phone text check (char_length(phone) <= 40),
    country text check (char_length(country) <= 80),
    markets text check (char_length(markets) <= 20),
    years_trading text check (char_length(years_trading) <= 20),
    activity text check (char_length(activity) <= 40),
    tools text check (char_length(tools) <= 600),
    why text check (char_length(why) <= 3000),
    status text not null default 'pending' check (status in ('pending', 'approved', 'declined')),
    reviewed_by uuid,
    reviewed_at timestamptz
);

alter table public.beta_requests add column if not exists phone text check (char_length(phone) <= 40);
alter table public.beta_requests add column if not exists years_trading text check (char_length(years_trading) <= 20);

alter table public.beta_requests enable row level security;
revoke all on public.beta_requests from public;
revoke all on public.beta_requests from anon;
revoke all on public.beta_requests from authenticated;
grant insert (name, email, phone, country, markets, years_trading, activity, tools, why) on public.beta_requests to anon;

drop policy if exists beta_requests_website_insert on public.beta_requests;
create policy beta_requests_website_insert
    on public.beta_requests
    for insert
    to anon
    with check (status = 'pending' and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$');

create or replace function public.signup_is_open()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select coalesce((select signup_open from public.beta_settings where id), false);
$$;

create or replace function public.beta_gate()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if public.signup_is_open() then
        return new;
    end if;
    if exists (
        select 1 from public.beta_access
        where email = lower(btrim(coalesce(new.email, '')))
    ) then
        return new;
    end if;
    raise exception 'Angstrom Signals is in closed beta. Request access at angstromsignals.com.';
end;
$$;

drop trigger if exists beta_gate on auth.users;
create trigger beta_gate
    before insert on auth.users
    for each row
    execute function public.beta_gate();

create or replace function public.admin_beta_requests()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce(
        (
            select jsonb_agg(
                jsonb_build_object(
                    'id', r.id,
                    'created_at', r.created_at,
                    'name', r.name,
                    'email', r.email,
                    'phone', r.phone,
                    'country', r.country,
                    'markets', r.markets,
                    'years_trading', r.years_trading,
                    'activity', r.activity,
                    'tools', r.tools,
                    'why', r.why,
                    'status', r.status
                )
                order by r.created_at desc
            )
            from public.beta_requests as r
        ),
        '[]'::jsonb
    );
end;
$$;

create or replace function public.review_beta_request(request_id bigint, decision text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    found_email text;
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    if decision not in ('approved', 'declined', 'pending') then
        return 'decision';
    end if;
    select lower(btrim(email)) into found_email
    from public.beta_requests
    where id = request_id;
    if found_email is null then
        return 'missing';
    end if;
    update public.beta_requests
    set status = decision, reviewed_by = auth.uid(), reviewed_at = now(), decided_via = 'dashboard'
    where id = request_id;
    if decision = 'approved' then
        insert into public.beta_access (email, created_by, request_id)
        values (found_email, auth.uid(), request_id)
        on conflict (email) do nothing;
    else
        delete from public.beta_access where email = found_email;
    end if;
    return 'ok';
end;
$$;

create or replace function public.admin_beta_access()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce(
        (
            select jsonb_agg(
                jsonb_build_object(
                    'email', a.email,
                    'created_at', a.created_at,
                    'has_account', exists (select 1 from auth.users u where lower(u.email) = a.email)
                )
                order by a.created_at desc
            )
            from public.beta_access as a
        ),
        '[]'::jsonb
    );
end;
$$;

create or replace function public.add_beta_email(address text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    clean text := lower(btrim(coalesce(address, '')));
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    if clean !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
        return 'email';
    end if;
    if exists (select 1 from public.beta_access where email = clean) then
        return 'exists';
    end if;
    insert into public.beta_requests (name, email, status, reviewed_by, reviewed_at, why)
    values ('(added by admin)', clean, 'approved', auth.uid(), now(), '');
    insert into public.beta_access (email, created_by) values (clean, auth.uid());
    return 'ok';
end;
$$;

create or replace function public.remove_beta_email(address text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    clean text := lower(btrim(coalesce(address, '')));
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    delete from public.beta_access where email = clean;
    if not found then
        return 'missing';
    end if;
    return 'ok';
end;
$$;

create or replace function public.admin_signup_open()
returns boolean
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return public.signup_is_open();
end;
$$;

create or replace function public.set_signup_open(open_now boolean)
returns text
language plpgsql
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        return 'forbidden';
    end if;
    update public.beta_settings set signup_open = coalesce(open_now, false) where id;
    return 'ok';
end;
$$;

revoke all on function public.signup_is_open() from public;
revoke all on function public.beta_gate() from public;
revoke all on function public.admin_beta_requests() from public;
revoke all on function public.review_beta_request(bigint, text) from public;
revoke all on function public.admin_beta_access() from public;
revoke all on function public.add_beta_email(text) from public;
revoke all on function public.remove_beta_email(text) from public;
revoke all on function public.admin_signup_open() from public;
revoke all on function public.set_signup_open(boolean) from public;

revoke all on function public.beta_gate() from anon;
revoke all on function public.beta_gate() from authenticated;
revoke all on function public.admin_beta_requests() from anon;
revoke all on function public.review_beta_request(bigint, text) from anon;
revoke all on function public.admin_beta_access() from anon;
revoke all on function public.add_beta_email(text) from anon;
revoke all on function public.remove_beta_email(text) from anon;
revoke all on function public.admin_signup_open() from anon;
revoke all on function public.set_signup_open(boolean) from anon;

grant execute on function public.signup_is_open() to anon;
grant execute on function public.signup_is_open() to authenticated;
grant execute on function public.admin_beta_requests() to authenticated;
grant execute on function public.review_beta_request(bigint, text) to authenticated;
grant execute on function public.admin_beta_access() to authenticated;
grant execute on function public.add_beta_email(text) to authenticated;
grant execute on function public.remove_beta_email(text) to authenticated;
grant execute on function public.admin_signup_open() to authenticated;
grant execute on function public.set_signup_open(boolean) to authenticated;

-- Before the first deploy that turns the closed beta on, add yourself and anyone already testing
-- (existing accounts keep working either way). The beta list only gates NEW accounts.


-- ------------------------------------------------------------------
-- Approve and Reject links in the beta request email.
-- Each link carries a signature only the website server and this database can make, so nobody can
-- approve themselves. The links open a confirm page first. Nothing changes until the button is pressed.
-- ------------------------------------------------------------------

create extension if not exists pgcrypto with schema extensions;

alter table public.beta_settings add column if not exists link_secret text;
alter table public.beta_requests add column if not exists request_ref text;
alter table public.beta_requests add column if not exists decided_via text;
alter table public.beta_requests add column if not exists notified_at timestamptz;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'beta_requests_ref_shape') then
        alter table public.beta_requests
            add constraint beta_requests_ref_shape check (request_ref is null or request_ref ~ '^[0-9a-f]{32}$');
    end if;
    if not exists (select 1 from pg_constraint where conname = 'beta_requests_decided_via_shape') then
        alter table public.beta_requests
            add constraint beta_requests_decided_via_shape check (decided_via is null or decided_via in ('dashboard', 'email'));
    end if;
end;
$$;

create unique index if not exists beta_requests_ref_key on public.beta_requests (request_ref) where request_ref is not null;

-- Requests decided before this feature, or in the dashboard, never need a worker email.
update public.beta_requests
set notified_at = coalesce(reviewed_at, now())
where notified_at is null and status <> 'pending' and decided_via is null;

grant insert (request_ref) on public.beta_requests to anon;

create or replace function public.beta_link_sig(p_ref text, p_action text)
returns text
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
    secret text;
begin
    select link_secret into secret from public.beta_settings where id;
    if secret is null or char_length(secret) < 16 then
        return null;
    end if;
    return encode(
        hmac(convert_to(coalesce(p_ref, '') || ':' || coalesce(p_action, ''), 'UTF8'), convert_to(secret, 'UTF8'), 'sha256'),
        'hex'
    );
end;
$$;

revoke all on function public.beta_link_sig(text, text) from public;
revoke all on function public.beta_link_sig(text, text) from anon;
revoke all on function public.beta_link_sig(text, text) from authenticated;

create or replace function public.beta_decision_preview(p_ref text, p_action text, p_sig text)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    wanted text;
    req record;
begin
    if p_action not in ('approve', 'reject') or coalesce(p_ref, '') !~ '^[0-9a-f]{32}$' then
        return jsonb_build_object('ok', false, 'reason', 'bad_link');
    end if;
    wanted := public.beta_link_sig(p_ref, p_action);
    if wanted is null then
        return jsonb_build_object('ok', false, 'reason', 'not_configured');
    end if;
    if p_sig is distinct from wanted then
        return jsonb_build_object('ok', false, 'reason', 'bad_link');
    end if;
    select name, email, markets, years_trading, activity, status into req
    from public.beta_requests where request_ref = p_ref;
    if not found then
        return jsonb_build_object('ok', false, 'reason', 'not_found');
    end if;
    return jsonb_build_object(
        'ok', true, 'name', req.name, 'email', req.email, 'markets', req.markets,
        'years', req.years_trading, 'activity', req.activity, 'status', req.status
    );
end;
$$;

create or replace function public.beta_decide(p_ref text, p_action text, p_sig text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    wanted text;
    new_status text;
    changed record;
    existing record;
begin
    if p_action not in ('approve', 'reject') or coalesce(p_ref, '') !~ '^[0-9a-f]{32}$' then
        return jsonb_build_object('ok', false, 'reason', 'bad_link');
    end if;
    wanted := public.beta_link_sig(p_ref, p_action);
    if wanted is null then
        return jsonb_build_object('ok', false, 'reason', 'not_configured');
    end if;
    if p_sig is distinct from wanted then
        return jsonb_build_object('ok', false, 'reason', 'bad_link');
    end if;
    new_status := case p_action when 'approve' then 'approved' else 'declined' end;

    update public.beta_requests
    set status = new_status, reviewed_at = now(), decided_via = 'email'
    where request_ref = p_ref and status = 'pending'
    returning id, name, email into changed;

    if not found then
        select name, email, status into existing from public.beta_requests where request_ref = p_ref;
        if not found then
            return jsonb_build_object('ok', false, 'reason', 'not_found');
        end if;
        return jsonb_build_object('ok', false, 'reason', 'already', 'status', existing.status, 'name', existing.name);
    end if;

    if new_status = 'approved' then
        insert into public.beta_access (email, request_id)
        values (lower(btrim(changed.email)), changed.id)
        on conflict (email) do nothing;
    else
        delete from public.beta_access where email = lower(btrim(changed.email));
    end if;
    return jsonb_build_object('ok', true, 'status', new_status, 'name', changed.name, 'email', changed.email);
end;
$$;

revoke all on function public.beta_decision_preview(text, text, text) from public;
revoke all on function public.beta_decide(text, text, text) from public;
grant execute on function public.beta_decision_preview(text, text, text) to anon, authenticated;
grant execute on function public.beta_decide(text, text, text) to anon, authenticated;

-- One-time setup, run by hand in the SQL editor: make the link secret, then copy the value it shows
-- into beta-config.php on the website as LINK_SECRET. Run it again only if you want new links.
--   update public.beta_settings
--   set link_secret = encode(extensions.gen_random_bytes(24), 'hex')
--   where id and link_secret is null
--   returning link_secret;

-- ---------------------------------------------------------------------------
-- Earnings date history
-- ---------------------------------------------------------------------------
-- asset_market keeps only the NEXT report date, so a date is lost once it passes.
-- This table keeps every date we have seen for a stock, when we first and last saw it,
-- so charts can mark past reports and later analysis can line price moves up with them.
-- A date that moved leaves its old row behind. last_seen_at close to report_date means
-- the date held until the report; an early last_seen_at means it was replaced.
-- Rows are written by a trigger on asset_market, never by the app, so history cannot be invented.
create table if not exists public.earnings_history (
    ticker text not null,
    report_date date not null,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    primary key (ticker, report_date)
);

alter table public.earnings_history enable row level security;

drop policy if exists "signed-in users read earnings history" on public.earnings_history;
create policy "signed-in users read earnings history" on public.earnings_history
    for select
    to authenticated
    using (true);

grant select on public.earnings_history to authenticated;

create or replace function public.keep_earnings_history()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.kind = 'Stock' and new.next_earnings is not null and new.asset_id is not null then
        insert into public.earnings_history (ticker, report_date)
        values (upper(new.asset_id), new.next_earnings)
        on conflict (ticker, report_date) do update set last_seen_at = now();
    end if;
    return null;
end;
$$;

revoke all on function public.keep_earnings_history() from public, anon, authenticated;

drop trigger if exists keep_earnings_history on public.asset_market;
create trigger keep_earnings_history
    after insert or update of next_earnings, earnings_checked_at on public.asset_market
    for each row execute function public.keep_earnings_history();

-- Start the history with the dates already stored.
insert into public.earnings_history (ticker, report_date)
select upper(asset_id), next_earnings
from public.asset_market
where kind = 'Stock' and next_earnings is not null and asset_id is not null
on conflict (ticker, report_date) do nothing;


-- ============================================================
-- Daily digest
-- ============================================================
-- instant_email: send an email at once for each crossing (on by default, as before).
-- digest_enabled: send one summary email a day instead of, or as well as, the instant ones.
-- digest_hour / digest_tz: when the digest goes out, in the person's own time zone.
-- last_digest_at: when the last digest (or quiet day) was recorded.
-- digested_at on a notification: this crossing has been included in a digest.
alter table public.alert_preferences
    add column if not exists instant_email boolean default true;
alter table public.alert_preferences
    add column if not exists digest_enabled boolean default false;
alter table public.alert_preferences
    add column if not exists digest_hour smallint default 8;
alter table public.alert_preferences
    add column if not exists digest_tz text default 'UTC';
alter table public.alert_preferences
    add column if not exists last_digest_at timestamptz;

alter table public.user_notifications
    add column if not exists digested_at timestamptz;


-- ============================================================
-- Market sentiment alerts
-- ============================================================
-- market_alerts_enabled: alert when the crypto or stock market sentiment score
-- reaches market_high_alert or drops to market_low_alert. Off by default.
-- These use the same instant and digest choices as asset score alerts. The
-- notification rows use asset_symbol market:crypto or market:stock.
alter table public.alert_preferences
    add column if not exists market_alerts_enabled boolean default false;
alter table public.alert_preferences
    add column if not exists market_high_alert numeric default 65;
alter table public.alert_preferences
    add column if not exists market_low_alert numeric default 35;


-- ============================================================
-- Estimated liquidation levels (crypto)
-- ============================================================
-- liq_levels: the strongest estimated long and short liquidation levels for a coin,
-- worked out by the background worker from Coinalyze data (see liquidation_levels.py).
-- liq_updated_at: when they were last worked out (about hourly).
-- Only the worker (service role) writes these; a signed-in session keeps what is stored.
alter table public.asset_market
    add column if not exists liq_levels jsonb;
alter table public.asset_market
    add column if not exists liq_updated_at timestamptz;

create or replace function public.guard_asset_market_liq()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if auth.uid() is null then
        return new;
    end if;
    if tg_op = 'INSERT' then
        new.liq_levels := null;
        new.liq_updated_at := null;
    else
        new.liq_levels := old.liq_levels;
        new.liq_updated_at := old.liq_updated_at;
    end if;
    return new;
end;
$$;

drop trigger if exists guard_asset_market_liq on public.asset_market;
create trigger guard_asset_market_liq
    before insert or update on public.asset_market
    for each row
    execute function public.guard_asset_market_liq();

-- 🌊 Your take on Tides (13 Nov 2026): 👍 agree or 👎 disagree with the Tide's current reading, and on 👎 your
-- own Tide score (stored 0..100 like every take, shown -100..+100), plus a short comment.
-- Takes and comments belong to the current reading (from the date it began, "since"), not to a day: Tides moves
-- slowly. They stay until the Tide changes to another reading; then tides_reset() clears them (the app calls it).
-- Comments use sentiment_comments with the key 'Tides|macro'; the 12-hour expiry of other comments skips that key.
-- Safe to run more than once. Adds one table and three functions, and redefines three comment functions (only the
-- Tides exception is new in them).

create table if not exists public.tides_votes (
    user_id uuid not null references auth.users (id) on delete cascade,
    since date not null,
    vote smallint not null check (vote in (1, -1)),
    alt_score smallint check (alt_score is null or alt_score between 0 and 100),
    created_at timestamptz not null default now(),
    primary key (user_id, since)
);

alter table public.tides_votes enable row level security;

drop policy if exists "own tides votes" on public.tides_votes;
create policy "own tides votes" on public.tides_votes
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.tides_votes to authenticated;

-- The crowd for the current reading: the same columns as market_mood_crowd, so the take box reads both alike.
create or replace function public.tides_crowd(p_since date)
returns table (
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
        (select count(*)::integer from public.tides_votes v where v.since = p_since and v.vote = 1),
        (select count(*)::integer from public.tides_votes v where v.since = p_since and v.vote = -1),
        (select v.vote from public.tides_votes v where v.since = p_since and v.user_id = auth.uid()),
        (select count(*)::integer from public.tides_votes v
          where v.since = p_since and v.vote = -1 and v.alt_score is not null),
        (select round(avg(v.alt_score), 1) from public.tides_votes v
          where v.since = p_since and v.vote = -1 and v.alt_score is not null),
        (select round(stddev_samp(v.alt_score), 1) from public.tides_votes v
          where v.since = p_since and v.vote = -1 and v.alt_score is not null),
        (select v.alt_score from public.tides_votes v where v.since = p_since and v.user_id = auth.uid());
$$;

revoke all on function public.tides_crowd(date) from public;
revoke all on function public.tides_crowd(date) from anon;
grant execute on function public.tides_crowd(date) to authenticated;

-- When the Tide changes to another reading: the takes and comments on the old one go (replies go with comments).
create or replace function public.tides_reset(p_since date)
returns void
language sql
security definer
set search_path = public
as $$
    delete from public.sentiment_comments
    where asset_key = 'Tides|macro' and sentiment_at < p_since::timestamptz;
    delete from public.tides_votes where since < p_since;
$$;

revoke all on function public.tides_reset(date) from public;
revoke all on function public.tides_reset(date) from anon;
grant execute on function public.tides_reset(date) to authenticated;

-- Other comments still expire after 12 hours; Tides comments wait for tides_reset().
create or replace function public.drop_expired_sentiment_comments()
returns void
language sql
security definer
set search_path = public
as $$
    delete from public.sentiment_comments
    where created_at < now() - interval '12 hours'
      and asset_key <> 'Tides|macro';
$$;

revoke all on function public.drop_expired_sentiment_comments() from public;
revoke all on function public.drop_expired_sentiment_comments() from anon;
grant execute on function public.drop_expired_sentiment_comments() to authenticated;

-- The comment and reply feeds as in supabase_rls.sql, with Tides comments kept beyond 12 hours.
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
      and (comments.created_at > now() - interval '12 hours' or comments.asset_key = 'Tides|macro')
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
    where (comments.created_at > now() - interval '12 hours' or comments.asset_key = 'Tides|macro')
      and (replies.created_at > now() - interval '12 hours' or comments.asset_key = 'Tides|macro')
    order by replies.created_at asc;
$$;

revoke all on function public.sentiment_replies() from public;
revoke all on function public.sentiment_replies() from anon;
grant execute on function public.sentiment_replies() to authenticated;

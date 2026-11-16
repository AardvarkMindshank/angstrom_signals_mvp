-- 17 Nov 2026: private conversations in the general chat.
-- Each message has an audience: everyone ('public'), one community ('group', its members and leader), or one
-- person ('direct', the two people). Only that audience can read it, here and through chat_feed. A reply keeps the
-- audience of the message it answers. A private message needs the recipient to accept it: not blocked either way,
-- and their "who can message me" choice (settings.dm_from: everyone, favourites, nobody). Blocks live in
-- settings.blocked (a list of account ids); a blocked person's messages are left out of your chat.
-- Safe to run more than once. Run it in the Supabase SQL editor.

alter table public.chat_messages add column if not exists audience text not null default 'public';
alter table public.chat_messages add column if not exists group_id bigint references public.user_groups (id) on delete cascade;
alter table public.chat_messages add column if not exists recipient_id uuid references auth.users (id) on delete cascade;

alter table public.chat_messages drop constraint if exists chat_messages_audience_shape;
alter table public.chat_messages add constraint chat_messages_audience_shape check (
    (audience = 'public' and group_id is null and recipient_id is null)
    or (audience = 'group' and group_id is not null and recipient_id is null)
    or (audience = 'direct' and recipient_id is not null and group_id is null and recipient_id <> user_id)
);

create index if not exists chat_messages_recipient_idx on public.chat_messages (recipient_id, created_at desc);
create index if not exists chat_messages_group_idx on public.chat_messages (group_id, created_at desc);

-- Is this account the leader or a member of the community?
create or replace function public.chat_in_group(chosen_group bigint, who uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (select 1 from public.user_groups where id = chosen_group and leader_id = who)
        or exists (select 1 from public.group_members where group_id = chosen_group and user_id = who);
$$;

-- One account's saved settings (who can message them, favourites, blocks).
create or replace function public.chat_settings(who uuid)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
    select coalesce((select settings from public.user_preferences where user_id = who), '{}'::jsonb);
$$;

-- May the sender start or continue a private conversation with the recipient?
create or replace function public.chat_may_message(sender uuid, recipient uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select sender is not null and recipient is not null and sender <> recipient
        and exists (select 1 from auth.users where id = recipient)
        and not coalesce(public.chat_settings(recipient) -> 'blocked' ? sender::text, false)
        and not coalesce(public.chat_settings(sender) -> 'blocked' ? recipient::text, false)
        and case coalesce(public.chat_settings(recipient) ->> 'dm_from', 'everyone')
                when 'nobody' then false
                when 'favourites' then coalesce(public.chat_settings(recipient) -> 'favourites' ? sender::text, false)
                else true
            end;
$$;

-- Who may read one message.
create or replace function public.chat_can_read(m_audience text, m_user uuid, m_group bigint, m_recipient uuid, who uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select m_audience = 'public'
        or m_user = who
        or (m_audience = 'direct' and m_recipient = who)
        or (m_audience = 'group' and public.chat_in_group(m_group, who));
$$;

revoke all on function public.chat_in_group(bigint, uuid) from public, anon;
revoke all on function public.chat_settings(uuid) from public, anon, authenticated;
revoke all on function public.chat_may_message(uuid, uuid) from public, anon;
revoke all on function public.chat_can_read(text, uuid, bigint, uuid, uuid) from public, anon;
grant execute on function public.chat_in_group(bigint, uuid) to authenticated;
grant execute on function public.chat_may_message(uuid, uuid) to authenticated;
grant execute on function public.chat_can_read(text, uuid, bigint, uuid, uuid) to authenticated;

drop policy if exists "read chat messages" on public.chat_messages;
create policy "read chat messages" on public.chat_messages
    for select
    to authenticated
    using (public.chat_can_read(audience, user_id, group_id, recipient_id, auth.uid()));

drop policy if exists "insert own chat message" on public.chat_messages;
create policy "insert own chat message" on public.chat_messages
    for insert
    to authenticated
    with check (
        auth.uid() = user_id
        and (
            audience = 'public'
            or (audience = 'group' and public.chat_in_group(group_id, auth.uid()))
            or (audience = 'direct' and public.chat_may_message(auth.uid(), recipient_id))
        )
    );

-- A reply answers a top-level message its writer can read, and keeps that message's audience.
create or replace function public.chat_message_parent()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    parent public.chat_messages%rowtype;
begin
    if new.parent_id is null then
        return new;
    end if;
    select * into parent from public.chat_messages where id = new.parent_id;
    if not found or parent.parent_id is not null then
        raise exception 'Reply to a top-level comment only';
    end if;
    if not public.chat_can_read(parent.audience, parent.user_id, parent.group_id, parent.recipient_id, new.user_id) then
        raise exception 'Reply to a top-level comment only';
    end if;
    new.audience := parent.audience;
    new.group_id := parent.group_id;
    if parent.audience = 'direct' then
        new.recipient_id := case when parent.user_id = new.user_id then parent.recipient_id else parent.user_id end;
    else
        new.recipient_id := null;
    end if;
    return new;
end;
$$;

drop trigger if exists chat_message_parent on public.chat_messages;
create trigger chat_message_parent
    before insert or update on public.chat_messages
    for each row
    execute function public.chat_message_parent();

-- The newest threads you can read, with replies, thumbs and the audience. Messages from people you blocked are left out.
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
    social_score integer,
    audience text,
    group_id bigint,
    group_name text,
    recipient_id uuid,
    recipient_name text
)
language sql
stable
security definer
set search_path = public
as $$
    with me as (
        select auth.uid() as uid, coalesce(public.chat_settings(auth.uid()) -> 'blocked', '[]'::jsonb) as blocked
    ),
    visible as (
        select chat_messages.*
        from public.chat_messages, me
        where public.chat_can_read(chat_messages.audience, chat_messages.user_id, chat_messages.group_id,
                                   chat_messages.recipient_id, me.uid)
          and not (me.blocked ? chat_messages.user_id::text)
    ),
    roots as (
        select visible.id
        from visible
        where visible.parent_id is null
        order by visible.created_at desc
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
        coalesce(profiles.social_score, 0),
        messages.audience,
        messages.group_id,
        groups.name,
        messages.recipient_id,
        coalesce(
            nullif(btrim(recipient_profiles.display_name), ''),
            nullif(split_part(recipients.email, '@', 1), ''),
            case when messages.recipient_id is null then null else 'Member' end
        )
    from visible as messages
    left join public.profiles as profiles
      on profiles.user_id = messages.user_id
    left join auth.users as users
      on users.id = messages.user_id
    left join public.user_groups as groups
      on groups.id = messages.group_id
    left join public.profiles as recipient_profiles
      on recipient_profiles.user_id = messages.recipient_id
    left join auth.users as recipients
      on recipients.id = messages.recipient_id
    where messages.id in (select roots.id from roots)
       or messages.parent_id in (select roots.id from roots);
$$;

revoke all on function public.chat_feed() from public;
revoke all on function public.chat_feed() from anon;
grant execute on function public.chat_feed() to authenticated;

-- "Find a person": members with a display name that starts with (or contains) what was typed. Names only, never emails.
drop function if exists public.chat_find_people(text);
create function public.chat_find_people(typed text)
returns table (id uuid, name text, avatar_url text, social_score integer)
language sql
stable
security definer
set search_path = public
as $$
    select profiles.user_id, btrim(profiles.display_name), profiles.avatar_url, coalesce(profiles.social_score, 0)
    from public.profiles as profiles
    where char_length(btrim(coalesce(typed, ''))) >= 2
      and nullif(btrim(profiles.display_name), '') is not null
      and profiles.user_id <> auth.uid()
      and profiles.display_name ilike '%' || replace(replace(replace(btrim(typed), '\', '\\'), '%', '\%'), '_', '\_') || '%'
    order by (profiles.display_name ilike replace(replace(replace(btrim(typed), '\', '\\'), '%', '\%'), '_', '\_') || '%') desc,
             profiles.display_name
    limit 10;
$$;

revoke all on function public.chat_find_people(text) from public, anon;
grant execute on function public.chat_find_people(text) to authenticated;

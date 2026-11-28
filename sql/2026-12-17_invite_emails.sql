-- Invite a friend: the background worker (beta_worker.py) now emails each new invite, from either app, once.
-- invite_again lets the inviter send the email again, at most once a day per address. Safe to run more than once.

alter table public.invites add column if not exists emailed_at timestamptz;
-- Invites saved before today were already emailed by the classic app.
update public.invites set emailed_at = coalesce(created_at, now()) where emailed_at is null;

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
    new.emailed_at := null;
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

-- 'ok' (the worker emails it again within five minutes), 'recent' (emailed in the last day), 'joined', or 'missing'.
create or replace function public.invite_again(address text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    rec public.invites%rowtype;
begin
    if me is null then
        return 'missing';
    end if;
    select * into rec from public.invites
    where inviter_id = me and email = lower(btrim(coalesce(address, '')));
    if rec.id is null then
        return 'missing';
    end if;
    if rec.credited_at is not null then
        return 'joined';
    end if;
    if rec.emailed_at is not null and rec.emailed_at > now() - interval '1 day' then
        return 'recent';
    end if;
    update public.invites set emailed_at = null where id = rec.id;
    return 'ok';
end;
$$;

revoke all on function public.invite_again(text) from public;
revoke all on function public.invite_again(text) from anon;
grant execute on function public.invite_again(text) to authenticated;

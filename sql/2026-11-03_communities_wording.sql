-- Communities wording (was "group") in the two notifications the database writes:
--   "<name> invited you to the community <name>." and "<name> joined your community <name>."
-- Replaces create_group_invite and respond_group_invite with the same logic and new wording only.
-- Safe to run more than once. Notifications already sent keep their old text. Tables and data are unchanged.

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
        inviter_label || ' invited you to the community ' || gname || '.'
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
        who || ' joined your community ' || gname || '.'
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

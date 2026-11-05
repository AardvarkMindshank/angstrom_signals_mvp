-- Open Prism scheduled scans to every signed-in account (design: docs/design/lattice_prism.md §8, build stage 5).
-- Safe to run more than once. Replaces one function, prism_save_scan, without the admin-only check. Everything else
-- stays as sql/2026-11-06_prism_scans.sql made it: owner-only reads, writes only through the functions, one run per
-- scan, market and cutoff, and at most 5 active scans per account.

create or replace function public.prism_save_scan(p_id uuid, p_name text, p_set jsonb, p_source jsonb,
                                                  p_schedule jsonb, p_alert_mode text, p_notify jsonb,
                                                  p_paused boolean)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    sid uuid;
    active integer;
    old_body jsonb;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    if p_set is null or p_set->>'schema' <> 'angstrom.set/1' or not (p_set ? 'decision') then
        raise exception 'set_not_scannable';
    end if;
    if pg_column_size(p_set) > 262144 then raise exception 'too_large'; end if;
    if p_schedule is null or not (p_schedule->>'kind' in ('close', 'times')) then raise exception 'bad_schedule'; end if;
    if p_schedule->>'kind' = 'close' and not (p_schedule->>'timeframe' in ('4H', '1D', '1W')) then
        raise exception 'bad_schedule';
    end if;
    if p_schedule->>'kind' = 'times' and (jsonb_typeof(p_schedule->'times') <> 'array'
        or jsonb_array_length(p_schedule->'times') not between 1 and 4) then
        raise exception 'bad_schedule';
    end if;
    if not (coalesce(p_alert_mode, 'change') in ('change', 'every')) then raise exception 'bad_alert_mode'; end if;

    if not coalesce(p_paused, false) then
        select count(*) into active from public.prism_scans
         where owner_id = me and not paused and id is distinct from p_id;
        if active >= 5 then raise exception 'too_many_active_scans'; end if;
    end if;

    if p_id is null then
        insert into public.prism_scans (owner_id, name, set_body, set_source, schedule, alert_mode, notify, paused)
        values (me, btrim(p_name), p_set, coalesce(p_source, '{}'::jsonb), p_schedule, coalesce(p_alert_mode, 'change'),
                coalesce(p_notify, '{"in_app": true, "email": true}'::jsonb), coalesce(p_paused, false))
        returning id into sid;
        return sid;
    end if;

    select set_body into old_body from public.prism_scans where id = p_id and owner_id = me;
    if not found then raise exception 'not_owner'; end if;
    update public.prism_scans
       set name = btrim(p_name), set_body = p_set, set_source = coalesce(p_source, set_source),
           set_version = set_version + (case when old_body = p_set then 0 else 1 end),
           schedule = p_schedule, alert_mode = coalesce(p_alert_mode, alert_mode), notify = coalesce(p_notify, notify),
           paused = coalesce(p_paused, paused), updated_at = now()
     where id = p_id and owner_id = me;
    return p_id;
end;
$$;

revoke all on function public.prism_save_scan(uuid, text, jsonb, jsonb, jsonb, text, jsonb, boolean) from public, anon;
grant execute on function public.prism_save_scan(uuid, text, jsonb, jsonb, jsonb, text, jsonb, boolean) to authenticated;

-- Built-in alert scans and "re-arm when" for Prism (design: docs/design/prism_builtin_alerts.md).
-- Safe to run more than once. Adds two columns and replaces two functions; nothing existing is removed.
--
--  * builtin: the Trend, Stretch and Flow alerts are now Prism scans, one per reading and direction per account
--    ("trend_up", "trend_down", "stretch_up", ...). The background worker creates them. They always run at each
--    daily close on the whole Watchlist, can't be paused or deleted, and don't count towards the 5 scheduled scans.
--    Their owner can change the Set (the line), the re-arm rule, where alerts go, and snoozes.
--  * rearm: an optional Set with a decision. When present, an asset that has alerted can alert again only after
--    this Set says Yes for it (for example "Trend at or below +30" after "Trend at least +50"), instead of after
--    any No. A small wobble around the line then doesn't alert again.

alter table public.prism_scans add column if not exists builtin text;
alter table public.prism_scans add column if not exists rearm jsonb;
create unique index if not exists prism_scans_one_builtin on public.prism_scans (owner_id, builtin)
    where builtin is not null;

create or replace function public.prism_put_scan(p_id uuid, p_scan jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    sid uuid;
    active integer;
    was_paused boolean;
    old_body jsonb;
    old_builtin text;
    old_channel text;
    v_name text := btrim(coalesce(p_scan->>'name', ''));
    v_set jsonb := p_scan->'set';
    v_rearm jsonb := p_scan->'rearm';
    v_schedule jsonb := p_scan->'schedule';
    v_notify jsonb := coalesce(p_scan->'notify', '{"channel": "instant", "on_yes": true}'::jsonb);
    v_assets jsonb := coalesce(p_scan->'assets', '[{"group": "watchlist"}]'::jsonb);
    v_snoozes jsonb := coalesce(p_scan->'snoozes', '{}'::jsonb);
    v_paused boolean := coalesce((p_scan->>'paused')::boolean, false);
    item jsonb;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    if p_id is not null then
        select builtin, notify->>'channel' into old_builtin, old_channel
          from public.prism_scans where id = p_id and owner_id = me;
        if not found then raise exception 'not_owner'; end if;
    end if;
    if char_length(v_name) not between 1 and 80 then raise exception 'bad_name'; end if;
    if v_set is null or v_set->>'schema' <> 'angstrom.set/1' or not (v_set ? 'decision') then
        raise exception 'set_not_scannable';
    end if;
    if jsonb_typeof(v_rearm) = 'null' then v_rearm := null; end if;
    if v_rearm is not null and (v_rearm->>'schema' <> 'angstrom.set/1' or not (v_rearm ? 'decision')) then
        raise exception 'bad_rearm';
    end if;
    if pg_column_size(p_scan) > 393216 then raise exception 'too_large'; end if;
    if v_schedule is null or not (v_schedule->>'kind' in ('close', 'times', 'manual')) then
        raise exception 'bad_schedule';
    end if;
    if v_schedule->>'kind' = 'close' and not (v_schedule->>'timeframe' in ('4H', '1D', '1W')) then
        raise exception 'bad_schedule';
    end if;
    if v_schedule->>'kind' = 'times' and (jsonb_typeof(v_schedule->'times') <> 'array'
        or jsonb_array_length(v_schedule->'times') not between 1 and 4) then
        raise exception 'bad_schedule';
    end if;
    if jsonb_typeof(v_notify) <> 'object' or not (coalesce(v_notify->>'channel', 'instant')
        in ('instant', 'digest', 'app', 'off', 'account')) then
        raise exception 'bad_alerts';
    end if;
    if jsonb_typeof(v_assets) <> 'array' or jsonb_array_length(v_assets) not between 1 and 60 then
        raise exception 'bad_assets';
    end if;
    for item in select * from jsonb_array_elements(v_assets) loop
        if not ((item->>'group') in ('watchlist', 'crypto', 'shares')
                or ((item->>'kind') in ('crypto', 'equity') and char_length(coalesce(item->>'id', '')) between 1 and 60))
        then
            raise exception 'bad_assets';
        end if;
    end loop;
    if jsonb_typeof(v_snoozes) <> 'object' or (select count(*) from jsonb_object_keys(v_snoozes)) > 100 then
        raise exception 'bad_snoozes';
    end if;

    if old_builtin is not null then
        -- A built-in alert: only its Set (the line), re-arm rule, alerts and snoozes change. Switching its alerts
        -- back on records the current answers quietly first, as switching an alert on always has.
        update public.prism_scans
           set set_body = v_set, rearm = v_rearm, notify = v_notify, snoozes = v_snoozes,
               set_version = set_version + (case when set_body = v_set then 0 else 1 end),
               quiet_next = quiet_next or (old_channel = 'off' and coalesce(v_notify->>'channel', 'instant') <> 'off'),
               updated_at = now()
         where id = p_id and owner_id = me;
        return p_id;
    end if;

    if not v_paused and v_schedule->>'kind' <> 'manual' then
        select count(*) into active from public.prism_scans
         where owner_id = me and not paused and coalesce(schedule->>'kind', 'close') <> 'manual'
           and builtin is null and id is distinct from p_id;
        if active >= 5 then raise exception 'too_many_active_scans'; end if;
    end if;

    if p_id is null then
        insert into public.prism_scans (owner_id, name, set_body, set_source, schedule, alert_mode, notify, paused,
                                        assets, snoozes, rearm)
        values (me, v_name, v_set, coalesce(p_scan->'source', '{}'::jsonb), v_schedule, 'change', v_notify, v_paused,
                v_assets, v_snoozes, v_rearm)
        returning id into sid;
        return sid;
    end if;

    select paused, set_body into was_paused, old_body from public.prism_scans where id = p_id and owner_id = me;
    update public.prism_scans
       set name = v_name, set_body = v_set, set_source = coalesce(p_scan->'source', set_source),
           set_version = set_version + (case when old_body = v_set then 0 else 1 end),
           schedule = v_schedule, notify = v_notify, paused = v_paused, assets = v_assets, snoozes = v_snoozes,
           rearm = v_rearm, quiet_next = quiet_next or (was_paused and not v_paused), updated_at = now()
     where id = p_id and owner_id = me;
    return p_id;
end;
$$;

create or replace function public.prism_delete_scan(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if exists (select 1 from public.prism_scans where id = p_id and owner_id = auth.uid() and builtin is not null) then
        raise exception 'builtin_scan';
    end if;
    delete from public.prism_scans where id = p_id and owner_id = auth.uid() and auth.uid() is not null;
    if not found then raise exception 'not_owner'; end if;
end;
$$;

revoke all on function public.prism_put_scan(uuid, jsonb), public.prism_delete_scan(uuid) from public, anon;
grant execute on function public.prism_put_scan(uuid, jsonb), public.prism_delete_scan(uuid) to authenticated;

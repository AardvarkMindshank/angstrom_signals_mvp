-- Prism Scans as saved objects (build stage 7, docs/design/lattice_stage7_report.md).
-- Safe to run more than once. Adds columns to prism_scans and one function; nothing existing is removed.
--
-- Each scan now keeps:
--  * assets: which assets it scans. Groups that follow the Watchlist ({"group": "watchlist" | "crypto" | "shares"})
--    and fixed assets ({"kind": "crypto" | "equity", "id": "..."}). Old scans default to the whole Watchlist.
--  * notify: {"channel": "instant" | "digest" | "app" | "off", "on_yes": true, "on_no": false, "on_fail": false}.
--  * snoozes: {"<kind>:<id>": "<until, ISO time>"}: no alerts for that asset on this scan until then.
--  * quiet_next: set when a paused scan is resumed, so its first run after resuming records answers without alerting.
--  * schedule kind "manual": run only with the Play button. Manual and paused scans don't count towards the 5.

alter table public.prism_scans add column if not exists assets jsonb not null default '[{"group": "watchlist"}]'::jsonb;
alter table public.prism_scans add column if not exists snoozes jsonb not null default '{}'::jsonb;
alter table public.prism_scans add column if not exists quiet_next boolean not null default false;

-- Create (p_id null) or replace one of your scans from one object. Returns its id.
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
    v_name text := btrim(coalesce(p_scan->>'name', ''));
    v_set jsonb := p_scan->'set';
    v_schedule jsonb := p_scan->'schedule';
    v_notify jsonb := coalesce(p_scan->'notify', '{"channel": "instant", "on_yes": true}'::jsonb);
    v_assets jsonb := coalesce(p_scan->'assets', '[{"group": "watchlist"}]'::jsonb);
    v_snoozes jsonb := coalesce(p_scan->'snoozes', '{}'::jsonb);
    v_paused boolean := coalesce((p_scan->>'paused')::boolean, false);
    item jsonb;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    if char_length(v_name) not between 1 and 80 then raise exception 'bad_name'; end if;
    if v_set is null or v_set->>'schema' <> 'angstrom.set/1' or not (v_set ? 'decision') then
        raise exception 'set_not_scannable';
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
        in ('instant', 'digest', 'app', 'off')) then
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

    if not v_paused and v_schedule->>'kind' <> 'manual' then
        select count(*) into active from public.prism_scans
         where owner_id = me and not paused and coalesce(schedule->>'kind', 'close') <> 'manual'
           and id is distinct from p_id;
        if active >= 5 then raise exception 'too_many_active_scans'; end if;
    end if;

    if p_id is null then
        insert into public.prism_scans (owner_id, name, set_body, set_source, schedule, alert_mode, notify, paused,
                                        assets, snoozes)
        values (me, v_name, v_set, coalesce(p_scan->'source', '{}'::jsonb), v_schedule, 'change', v_notify, v_paused,
                v_assets, v_snoozes)
        returning id into sid;
        return sid;
    end if;

    select paused, set_body into was_paused, old_body from public.prism_scans where id = p_id and owner_id = me;
    if not found then raise exception 'not_owner'; end if;
    update public.prism_scans
       set name = v_name, set_body = v_set, set_source = coalesce(p_scan->'source', set_source),
           set_version = set_version + (case when old_body = v_set then 0 else 1 end),
           schedule = v_schedule, notify = v_notify, paused = v_paused, assets = v_assets, snoozes = v_snoozes,
           quiet_next = quiet_next or (was_paused and not v_paused), updated_at = now()
     where id = p_id and owner_id = me;
    return p_id;
end;
$$;

revoke all on function public.prism_put_scan(uuid, jsonb) from public, anon;
grant execute on function public.prism_put_scan(uuid, jsonb) to authenticated;

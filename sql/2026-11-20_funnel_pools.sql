-- Funnels v2: a pool rule on each funnel (docs/design/funnels_v2_spec.md). Safe to run more than once.
-- Needs sql/2026-11-17_funnels.sql and sql/2026-11-18_equity_funnels.sql first.
--
--  * funnels.pool     {"top": 50|100|200|500, "min_volume": dollars a day, "watchlist_only": true|false}; {} = the whole
--                     eligible universe (as before).
--  * funnel_save      takes the pool too (the earlier versions still work and keep the pool as it is).

alter table public.funnels add column if not exists pool jsonb not null default '{}'::jsonb;

create or replace function public.funnel_save(p_id uuid, p_name text, p_direction text, p_stages jsonb,
                                              p_flicker boolean, p_alerts jsonb, p_paused boolean, p_market text,
                                              p_pool jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    fid uuid;
    old_stages jsonb;
    old_pool jsonb;
    stage jsonb;
    v_pool jsonb := coalesce(p_pool, '{}'::jsonb);
begin
    if me is null then raise exception 'not_signed_in'; end if;
    if not (p_direction in ('long', 'short')) then raise exception 'bad_direction'; end if;
    if not (coalesce(p_market, 'crypto') in ('crypto', 'equity')) then raise exception 'bad_market'; end if;
    if p_stages is null or jsonb_typeof(p_stages) <> 'array' or jsonb_array_length(p_stages) not between 3 and 5 then
        raise exception 'bad_stages';
    end if;
    for stage in select * from jsonb_array_elements(p_stages) loop
        if not (stage->>'timeframe' in ('15m', '30m', '1h', '4h', '12h', '1D', '1W'))
           or stage->'set_body'->>'schema' <> 'angstrom.set/1' or not (stage->'set_body' ? 'decision') then
            raise exception 'bad_stages';
        end if;
    end loop;
    if jsonb_typeof(v_pool) <> 'object'
       or (v_pool ? 'top' and not (v_pool->>'top' in ('50', '100', '200', '500')))
       or (v_pool ? 'min_volume' and ((v_pool->>'min_volume')::numeric < 0 or (v_pool->>'min_volume')::numeric > 1e10))
       or (v_pool ? 'watchlist_only' and jsonb_typeof(v_pool->'watchlist_only') <> 'boolean') then
        raise exception 'bad_pool';
    end if;
    if pg_column_size(p_stages) > 524288 then raise exception 'too_large'; end if;

    if p_id is null then
        if (select count(*) from public.funnels where owner_id = me) >= 6 then raise exception 'too_many_funnels'; end if;
        insert into public.funnels (owner_id, name, direction, stages, flicker, alerts, paused, market, pool)
        values (me, btrim(p_name), p_direction, p_stages, coalesce(p_flicker, true),
                coalesce(p_alerts, '{"in_app": true, "email": false}'::jsonb), coalesce(p_paused, false),
                coalesce(p_market, 'crypto'), v_pool)
        returning id into fid;
        return fid;
    end if;

    select f.stages, f.pool into old_stages, old_pool from public.funnels f where f.id = p_id and f.owner_id = me;
    if not found then raise exception 'not_owner'; end if;
    update public.funnels
       set name = btrim(p_name), direction = p_direction, stages = p_stages, flicker = coalesce(p_flicker, flicker),
           alerts = coalesce(p_alerts, alerts), paused = coalesce(p_paused, paused), pool = v_pool,
           stages_version = stages_version + (case when old_stages = p_stages and old_pool = v_pool then 0 else 1 end),
           updated_at = now()
     where id = p_id and owner_id = me;
    return p_id;
end;
$$;

revoke all on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean, text, jsonb) from public, anon;
grant execute on function public.funnel_save(uuid, text, text, jsonb, boolean, jsonb, boolean, text, jsonb) to authenticated;

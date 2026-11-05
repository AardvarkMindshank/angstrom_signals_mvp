-- Prism scheduled scans (design: docs/design/lattice_prism.md §5.2, build stage 3).
-- Safe to run more than once. Adds three tables and three functions; changes nothing that exists.
--
-- Rules enforced here, on the server:
--  * Signed-in users never write these tables directly: every change goes through a security-definer function.
--  * Owners read their own scans, runs and latches. The background worker uses the service role.
--  * One run per (scan, market, cutoff): the unique key is the worker's claim, so a retry never repeats a run or its
--    alerts.
--  * At most 5 active (not paused) scans per account. While Prism is in preview, only admin accounts can save scans.

create table if not exists public.prism_scans (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users (id) on delete cascade,
    name text not null check (char_length(btrim(name)) between 1 and 80),
    set_body jsonb not null,                       -- a pinned copy of one Set version, with its decision
    set_source jsonb not null default '{}'::jsonb, -- where it came from: {config, version} or {demo}
    set_version integer not null default 1,        -- bumped when the owner pins a different Set
    schedule jsonb not null,                       -- {kind: close, timeframe} or {kind: times, times, tz, days}
    alert_mode text not null default 'change' check (alert_mode in ('change', 'every')),
    notify jsonb not null default '{"in_app": true, "email": true}'::jsonb,
    paused boolean not null default false,
    last_run_at timestamptz,
    latches_reset_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.prism_scan_runs (
    id bigint generated always as identity primary key,
    scan_id uuid not null references public.prism_scans (id) on delete cascade,
    market text not null check (market in ('crypto', 'equity')),
    cutoff timestamptz not null,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'running' check (status in ('running', 'ok', 'failed')),
    late_seconds integer,
    set_version integer,
    results jsonb,          -- per asset: kind, id, asset, answer, how_sure, reason, available
    opened jsonb,           -- asset keys whose alert opened on this run
    released jsonb,         -- asset keys released by a confirmed No
    record jsonb,           -- the replay record: inputs, input hashes, code identity
    error text,
    unique (scan_id, market, cutoff)
);

create table if not exists public.prism_scan_latches (
    scan_id uuid not null references public.prism_scans (id) on delete cascade,
    asset_key text not null,
    opened_at timestamptz not null default now(),
    primary key (scan_id, asset_key)
);

create index if not exists prism_scans_owner on public.prism_scans (owner_id);
create index if not exists prism_runs_scan on public.prism_scan_runs (scan_id, cutoff desc);

alter table public.prism_scans enable row level security;
alter table public.prism_scan_runs enable row level security;
alter table public.prism_scan_latches enable row level security;

drop policy if exists "owners read their scans" on public.prism_scans;
create policy "owners read their scans" on public.prism_scans
    for select to authenticated using (owner_id = auth.uid());
drop policy if exists "owners read their scan runs" on public.prism_scan_runs;
create policy "owners read their scan runs" on public.prism_scan_runs
    for select to authenticated
    using (exists (select 1 from public.prism_scans s where s.id = scan_id and s.owner_id = auth.uid()));
drop policy if exists "owners read their scan latches" on public.prism_scan_latches;
create policy "owners read their scan latches" on public.prism_scan_latches
    for select to authenticated
    using (exists (select 1 from public.prism_scans s where s.id = scan_id and s.owner_id = auth.uid()));

revoke all on public.prism_scans, public.prism_scan_runs, public.prism_scan_latches from anon, authenticated;
grant select on public.prism_scans, public.prism_scan_runs, public.prism_scan_latches to authenticated;

-- ------------------------------------------------------------------------------------------------ writing

-- Create (p_id null) or change one of your scans. Returns its id. The worker validates the Set again before every
-- run with the full validator; this checks shape, size, schedule and limits.
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
    if not public.is_admin() then                  -- supabase_rls.sql; removed when Prism opens to everyone
        raise exception 'prism_preview_admins_only';
    end if;
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

create or replace function public.prism_delete_scan(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.prism_scans where id = p_id and owner_id = auth.uid() and auth.uid() is not null;
    if not found then raise exception 'not_owner'; end if;
end;
$$;

-- Forget which assets have already alerted, so each current Yes alerts once more on the next run.
create or replace function public.prism_reset_latches(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not exists (select 1 from public.prism_scans where id = p_id and owner_id = auth.uid() and auth.uid() is not null)
    then raise exception 'not_owner'; end if;
    delete from public.prism_scan_latches where scan_id = p_id;
    update public.prism_scans set latches_reset_at = now(), updated_at = now() where id = p_id;
end;
$$;

revoke all on function public.prism_save_scan(uuid, text, jsonb, jsonb, jsonb, text, jsonb, boolean),
    public.prism_delete_scan(uuid), public.prism_reset_latches(uuid) from public, anon;
grant execute on function public.prism_save_scan(uuid, text, jsonb, jsonb, jsonb, text, jsonb, boolean),
    public.prism_delete_scan(uuid), public.prism_reset_latches(uuid) to authenticated;

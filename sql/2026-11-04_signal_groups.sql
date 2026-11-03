-- Signal Groups and Signal Sets: versioned storage, publication and sharing (design: docs/design/groups_sets.md §6–7).
-- Safe to run more than once. Adds five tables and their functions; changes nothing that exists.
--
-- Rules enforced here, on the server:
--  * Signed-in users never write these tables directly: every change goes through a security-definer function.
--  * Version content is immutable. Publication and sharing are separate, logged, owner-only metadata.
--  * Strict capture ceilings: when a version is saved or copied, the server records the effective audience of every
--    source it captured; publishing that version to audience X requires X within its capture ceiling and within each
--    source's effective audience now. A ceiling never rises; re-capture in a new version to redistribute.
--  * Submitted provenance is never trusted: the server re-reads each source version, checks the embedded snapshot is
--    identical, and writes the provenance (owner, version, content hash, capture time, ceiling) itself.
--
-- Audiences are jsonb: {"owner": true} | {"communities": [ids]} | {"public": true}.

create table if not exists public.analysis_configs (
    id uuid primary key default gen_random_uuid(),
    kind text not null check (kind in ('group', 'set')),
    owner_id uuid references auth.users (id) on delete cascade,       -- null = Angstrom starter
    starter_alias text unique,
    name text not null check (char_length(btrim(name)) between 1 and 80),
    current_version integer not null default 0,
    copied_from_config uuid references public.analysis_configs (id) on delete set null,
    copied_from_version integer,
    copy_ceiling jsonb,
    archived boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check ((owner_id is null) = (starter_alias is not null))
);

create table if not exists public.analysis_config_versions (
    config_id uuid not null references public.analysis_configs (id) on delete cascade,
    version integer not null check (version >= 1),
    schema text not null,
    body jsonb not null,
    content_sha256 text not null,
    lineage_version integer not null,
    capture_ceiling jsonb not null,
    dependencies jsonb not null default '[]'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    change_note text check (change_note is null or char_length(change_note) <= 300),
    primary key (config_id, version)
);

create table if not exists public.analysis_version_publications (
    config_id uuid not null,
    version integer not null,
    audience text not null check (audience in ('private', 'communities', 'public')),
    updated_at timestamptz not null default now(),
    updated_by uuid,
    primary key (config_id, version),
    foreign key (config_id, version) references public.analysis_config_versions (config_id, version) on delete cascade
);

create table if not exists public.analysis_version_shares (
    config_id uuid not null,
    version integer not null,
    user_group_id bigint not null references public.user_groups (id) on delete cascade,
    shared_by uuid,
    shared_at timestamptz not null default now(),
    primary key (config_id, version, user_group_id),
    foreign key (config_id, version) references public.analysis_config_versions (config_id, version) on delete cascade
);

create table if not exists public.analysis_publication_log (
    id bigint generated always as identity primary key,
    config_id uuid not null,
    version integer,
    action text not null,
    detail jsonb,
    actor uuid,
    at timestamptz not null default now()
);

create index if not exists analysis_configs_owner on public.analysis_configs (owner_id);
create index if not exists analysis_shares_group on public.analysis_version_shares (user_group_id);
create index if not exists analysis_log_config on public.analysis_publication_log (config_id, at desc);

-- Version rows never change.
create or replace function public.analysis_versions_immutable()
returns trigger
language plpgsql
as $$
begin
    raise exception 'analysis_config_versions rows are immutable';
end;
$$;

drop trigger if exists analysis_versions_immutable on public.analysis_config_versions;
create trigger analysis_versions_immutable
    before update on public.analysis_config_versions
    for each row
    execute function public.analysis_versions_immutable();

-- ------------------------------------------------------------------------------------------------ audience algebra

create or replace function public.analysis_meet(a jsonb, b jsonb)
returns jsonb
language plpgsql
immutable
as $$
declare
    common jsonb;
begin
    if a ? 'public' then return b; end if;
    if b ? 'public' then return a; end if;
    if a ? 'owner' or b ? 'owner' then return '{"owner": true}'::jsonb; end if;
    select coalesce(jsonb_agg(x order by x), '[]'::jsonb) into common
    from (select jsonb_array_elements(a -> 'communities') as x
          intersect
          select jsonb_array_elements(b -> 'communities')) s;
    if jsonb_array_length(common) = 0 then return '{"owner": true}'::jsonb; end if;
    return jsonb_build_object('communities', common);
end;
$$;

-- x within y: every reader of x can read y. Owner-only is within anything.
create or replace function public.analysis_within(x jsonb, y jsonb)
returns boolean
language plpgsql
immutable
as $$
begin
    if x ? 'owner' or y ? 'public' then return true; end if;
    if x ? 'public' then return false; end if;
    if y ? 'owner' then return false; end if;
    return not exists (select jsonb_array_elements(x -> 'communities')
                       except
                       select jsonb_array_elements(y -> 'communities'));
end;
$$;

create or replace function public.analysis_published(cfg uuid, ver integer)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
    select case coalesce(p.audience, 'private')
        when 'public' then '{"public": true}'::jsonb
        when 'communities' then jsonb_build_object('communities',
            coalesce((select jsonb_agg(to_jsonb(s.user_group_id) order by s.user_group_id)
                      from public.analysis_version_shares s
                      where s.config_id = cfg and s.version = ver), '[]'::jsonb))
        else '{"owner": true}'::jsonb end
    from (select 1) one
    left join public.analysis_version_publications p on p.config_id = cfg and p.version = ver;
$$;

-- Effective audience of a version now = what it is published to, limited by its capture ceiling.
create or replace function public.analysis_effective(cfg uuid, ver integer)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
    select public.analysis_meet(public.analysis_published(cfg, ver), v.capture_ceiling)
    from public.analysis_config_versions v
    where v.config_id = cfg and v.version = ver;
$$;

create or replace function public.analysis_in_audience(who uuid, aud jsonb)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select case
        when aud is null or who is null then false
        when aud ? 'public' then true
        when aud ? 'owner' then false
        else exists (
            select 1 from jsonb_array_elements(aud -> 'communities') c
            where exists (select 1 from public.user_groups g where g.id = (c #>> '{}')::bigint and g.leader_id = who)
               or exists (select 1 from public.group_members m where m.group_id = (c #>> '{}')::bigint and m.user_id = who))
    end;
$$;

create or replace function public.analysis_can_read(who uuid, cfg uuid, ver integer)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1 from public.analysis_configs c
        join public.analysis_config_versions v on v.config_id = c.id and v.version = ver
        where c.id = cfg
          and ((who is not null and c.owner_id = who)
               or public.analysis_in_audience(who, public.analysis_effective(cfg, ver))));
$$;

-- What the signed-in caller may read (the only read check exposed to signed-in users).
create or replace function public.analysis_can_read_me(cfg uuid, ver integer)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select public.analysis_can_read(auth.uid(), cfg, ver);
$$;

-- ------------------------------------------------------------------------------------------------ row-level security

alter table public.analysis_configs enable row level security;
alter table public.analysis_config_versions enable row level security;
alter table public.analysis_version_publications enable row level security;
alter table public.analysis_version_shares enable row level security;
alter table public.analysis_publication_log enable row level security;

drop policy if exists "read configs you own or can read a version of" on public.analysis_configs;
create policy "read configs you own or can read a version of" on public.analysis_configs
    for select to authenticated
    using (owner_id = auth.uid()
           or exists (select 1 from public.analysis_config_versions v
                      where v.config_id = analysis_configs.id and public.analysis_can_read_me(v.config_id, v.version)));

drop policy if exists "read versions you may read" on public.analysis_config_versions;
create policy "read versions you may read" on public.analysis_config_versions
    for select to authenticated
    using (public.analysis_can_read_me(config_id, version));

drop policy if exists "owners read their publications" on public.analysis_version_publications;
create policy "owners read their publications" on public.analysis_version_publications
    for select to authenticated
    using (exists (select 1 from public.analysis_configs c where c.id = config_id and c.owner_id = auth.uid()));

drop policy if exists "owners read their shares" on public.analysis_version_shares;
create policy "owners read their shares" on public.analysis_version_shares
    for select to authenticated
    using (exists (select 1 from public.analysis_configs c where c.id = config_id and c.owner_id = auth.uid()));

drop policy if exists "owners read their log" on public.analysis_publication_log;
create policy "owners read their log" on public.analysis_publication_log
    for select to authenticated
    using (exists (select 1 from public.analysis_configs c where c.id = config_id and c.owner_id = auth.uid()));

revoke all on public.analysis_configs, public.analysis_config_versions, public.analysis_version_publications,
    public.analysis_version_shares, public.analysis_publication_log from anon, authenticated;
grant select on public.analysis_configs, public.analysis_config_versions, public.analysis_version_publications,
    public.analysis_version_shares, public.analysis_publication_log to authenticated;

-- ------------------------------------------------------------------------------------------------ writing

-- Internal: insert the next version of a config the caller may write. Validates Set snapshots against their
-- sources, writes provenance, computes the capture ceiling and dependencies.
create or replace function public.analysis_insert_version(cfg uuid, body jsonb, note text, actor uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    c public.analysis_configs;
    next_version integer;
    ceiling jsonb;
    deps jsonb := '[]'::jsonb;
    new_body jsonb := body;
    g jsonb;
    i integer := 0;
    src_id uuid;
    src_ver integer;
    src public.analysis_config_versions;
    src_cfg public.analysis_configs;
    eff jsonb;
    limit_bytes integer;
begin
    select * into c from public.analysis_configs where id = cfg for update;
    limit_bytes := case c.kind when 'set' then 262144 else 65536 end;
    if octet_length(body::text) > limit_bytes then
        raise exception 'too_large' using hint = 'The document is larger than allowed.';
    end if;
    if body ->> 'schema' is distinct from (case c.kind when 'set' then 'angstrom.set/1' else 'angstrom.group/1' end) then
        raise exception 'wrong_schema';
    end if;
    if jsonb_typeof(body -> 'lineage_version') is distinct from 'number' then
        raise exception 'missing_lineage_version';
    end if;
    ceiling := coalesce(c.copy_ceiling, '{"public": true}'::jsonb);
    if c.kind = 'set' then
        for g in select * from jsonb_array_elements(coalesce(body -> 'groups', '[]'::jsonb)) loop
            src_ver := (g #>> '{provenance,source_version}')::integer;
            if (g #>> '{provenance,source_config}') like 'starter:%' then
                select id into src_id from public.analysis_configs where starter_alias = g #>> '{provenance,source_config}';
            else
                src_id := (g #>> '{provenance,source_config}')::uuid;
            end if;
            select * into src from public.analysis_config_versions where config_id = src_id and version = src_ver;
            select * into src_cfg from public.analysis_configs where id = src_id;
            if src.config_id is null or src_cfg.kind <> 'group' then
                raise exception 'unknown_source' using hint = coalesce(g #>> '{provenance,source_config}', '?');
            end if;
            if not public.analysis_can_read(actor, src_id, src_ver) then
                raise exception 'not_authorised_to_capture' using hint = src_id::text;
            end if;
            if (g -> 'snapshot') is distinct from src.body then
                raise exception 'snapshot_mismatch' using hint = src_id::text;
            end if;
            eff := public.analysis_effective(src_id, src_ver);
            ceiling := public.analysis_meet(ceiling, eff);
            deps := deps || jsonb_build_array(jsonb_build_object('config', src_id, 'version', src_ver, 'audience_at_capture', eff));
            new_body := jsonb_set(new_body, array['groups', i::text, 'provenance'], jsonb_build_object(
                'source_config', g #>> '{provenance,source_config}', 'source_version', src_ver,
                'source_owner', src_cfg.owner_id, 'content_sha256', src.content_sha256,
                'captured_at', now(), 'audience_ceiling', eff, 'computed_by', 'server'));
            i := i + 1;
        end loop;
    end if;
    next_version := c.current_version + 1;
    insert into public.analysis_config_versions
        (config_id, version, schema, body, content_sha256, lineage_version, capture_ceiling, dependencies, created_by, change_note)
    values (cfg, next_version, new_body ->> 'schema', new_body,
            encode(sha256(convert_to(new_body::text, 'UTF8')), 'hex'),
            (new_body ->> 'lineage_version')::integer, ceiling, deps, actor, note);
    insert into public.analysis_version_publications (config_id, version, audience, updated_by)
    values (cfg, next_version, 'private', actor);
    update public.analysis_configs
       set current_version = next_version, updated_at = now(), name = coalesce(nullif(btrim(new_body ->> 'name'), ''), name)
     where id = cfg;
    insert into public.analysis_publication_log (config_id, version, action, detail, actor)
    values (cfg, next_version, 'save', jsonb_build_object('capture_ceiling', ceiling, 'dependencies', deps), actor);
    return next_version;
end;
$$;

create or replace function public.analysis_create_config(kind text, body jsonb, note text default null)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    cfg uuid;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    insert into public.analysis_configs (kind, owner_id, name)
    values (kind, me, coalesce(nullif(btrim(body ->> 'name'), ''), 'Untitled'))
    returning id into cfg;
    perform public.analysis_insert_version(cfg, body, note, me);
    return cfg;
end;
$$;

create or replace function public.analysis_save_version(cfg uuid, expected_version integer, body jsonb, note text default null)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    c public.analysis_configs;
begin
    select * into c from public.analysis_configs where id = cfg for update;
    if c.id is null or c.owner_id is distinct from me or me is null then raise exception 'not_owner'; end if;
    if c.archived then raise exception 'archived'; end if;
    if c.current_version <> expected_version then
        raise exception 'conflict' using hint = format('current version is %s', c.current_version);
    end if;
    return public.analysis_insert_version(cfg, body, note, me);
end;
$$;

create or replace function public.analysis_copy_config(src uuid, src_version integer, new_name text default null)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    s public.analysis_config_versions;
    s_cfg public.analysis_configs;
    eff jsonb;
    cfg uuid;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    select * into s from public.analysis_config_versions where config_id = src and version = src_version;
    select * into s_cfg from public.analysis_configs where id = src;
    if s.config_id is null or not public.analysis_can_read(me, src, src_version) then
        raise exception 'not_authorised_to_copy';
    end if;
    eff := public.analysis_effective(src, src_version);
    insert into public.analysis_configs (kind, owner_id, name, copied_from_config, copied_from_version, copy_ceiling)
    values (s_cfg.kind, me, coalesce(nullif(btrim(new_name), ''), s_cfg.name), src, src_version, eff)
    returning id into cfg;
    perform public.analysis_insert_version(cfg, s.body, 'copied', me);
    insert into public.analysis_publication_log (config_id, version, action, detail, actor)
    values (cfg, 1, 'copy', jsonb_build_object('from', src, 'version', src_version, 'audience_at_copy', eff), me);
    return cfg;
end;
$$;

create or replace function public.analysis_publish_version(cfg uuid, ver integer, audience text, communities bigint[] default '{}')
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    c public.analysis_configs;
    v public.analysis_config_versions;
    want jsonb;
    dep jsonb;
    cid bigint;
begin
    select * into c from public.analysis_configs where id = cfg;
    if c.id is null or me is null or c.owner_id is distinct from me then raise exception 'not_owner'; end if;
    select * into v from public.analysis_config_versions where config_id = cfg and version = ver;
    if v.config_id is null then raise exception 'unknown_version'; end if;
    if audience = 'public' then
        want := '{"public": true}'::jsonb;
    elsif audience = 'communities' then
        if coalesce(array_length(communities, 1), 0) = 0 then raise exception 'no_communities'; end if;
        foreach cid in array communities loop
            if not public.analysis_in_audience(me, jsonb_build_object('communities', jsonb_build_array(cid))) then
                raise exception 'not_in_community' using hint = cid::text;
            end if;
        end loop;
        select jsonb_build_object('communities', jsonb_agg(to_jsonb(x) order by x)) into want
        from (select distinct unnest(communities) as x) s;
    elsif audience = 'private' then
        want := '{"owner": true}'::jsonb;
    else
        raise exception 'bad_audience';
    end if;
    if not public.analysis_within(want, v.capture_ceiling) then
        raise exception 'beyond_capture_ceiling' using hint = v.capture_ceiling::text;
    end if;
    for dep in select * from jsonb_array_elements(v.dependencies) loop
        if not public.analysis_within(want, public.analysis_effective((dep ->> 'config')::uuid, (dep ->> 'version')::integer)) then
            raise exception 'beyond_source_audience' using hint = dep ->> 'config';
        end if;
    end loop;
    insert into public.analysis_version_publications (config_id, version, audience, updated_at, updated_by)
    values (cfg, ver, audience, now(), me)
    on conflict (config_id, version) do update set audience = excluded.audience, updated_at = now(), updated_by = me;
    delete from public.analysis_version_shares where config_id = cfg and version = ver;
    if audience = 'communities' then
        insert into public.analysis_version_shares (config_id, version, user_group_id, shared_by)
        select cfg, ver, x, me from (select distinct unnest(communities) as x) s;
    end if;
    insert into public.analysis_publication_log (config_id, version, action, detail, actor)
    values (cfg, ver, 'publish', jsonb_build_object('audience', want), me);
end;
$$;

create or replace function public.analysis_archive_config(cfg uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    update public.analysis_configs set archived = true, updated_at = now()
     where id = cfg and owner_id = me and me is not null;
    if not found then raise exception 'not_owner'; end if;
    insert into public.analysis_publication_log (config_id, action, actor) values (cfg, 'archive', me);
end;
$$;

-- Starters: written by the service role only (the SQL editor or the worker).
create or replace function public.analysis_seed_starter(alias text, body jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    cfg uuid;
    current_body jsonb;
begin
    select id into cfg from public.analysis_configs where starter_alias = alias;
    if cfg is null then
        insert into public.analysis_configs (kind, owner_id, starter_alias, name)
        values ('group', null, alias, coalesce(body ->> 'name', alias)) returning id into cfg;
    else
        select v.body into current_body from public.analysis_config_versions v
         join public.analysis_configs c on c.id = v.config_id and v.version = c.current_version where c.id = cfg;
        if current_body = body then return cfg; end if;
    end if;
    perform public.analysis_insert_version(cfg, body, 'starter', null);
    update public.analysis_version_publications set audience = 'public'
     where config_id = cfg and version = (select current_version from public.analysis_configs where id = cfg);
    return cfg;
end;
$$;

revoke all on function public.analysis_insert_version(uuid, jsonb, text, uuid) from public, anon, authenticated;
revoke all on function public.analysis_seed_starter(text, jsonb) from public, anon, authenticated;
revoke all on function public.analysis_meet(jsonb, jsonb), public.analysis_within(jsonb, jsonb),
    public.analysis_published(uuid, integer), public.analysis_effective(uuid, integer),
    public.analysis_in_audience(uuid, jsonb), public.analysis_can_read(uuid, uuid, integer),
    public.analysis_versions_immutable() from public, anon, authenticated;
revoke all on function public.analysis_can_read_me(uuid, integer) from public, anon;
grant execute on function public.analysis_can_read_me(uuid, integer) to authenticated;
revoke all on function public.analysis_create_config(text, jsonb, text), public.analysis_save_version(uuid, integer, jsonb, text),
    public.analysis_copy_config(uuid, integer, text), public.analysis_publish_version(uuid, integer, text, bigint[]),
    public.analysis_archive_config(uuid) from public, anon;
grant execute on function public.analysis_create_config(text, jsonb, text), public.analysis_save_version(uuid, integer, jsonb, text),
    public.analysis_copy_config(uuid, integer, text), public.analysis_publish_version(uuid, integer, text, bigint[]),
    public.analysis_archive_config(uuid) to authenticated;
grant execute on function public.analysis_seed_starter(text, jsonb) to service_role;

-- Security tests for sql/2026-11-04_signal_groups.sql (design §7 acceptance requirement).
-- Runs on a throwaway Postgres with tests/pg/supabase_stub.sql: four signed-in users, two communities, anon.
-- Every scenario from the design's sharing table, plus direct-write refusal, immutability, forged provenance,
-- concurrent saves, leaving a community, per-version publication, starters and non-owner refusals.
\set ON_ERROR_STOP 1
set client_min_messages = warning;

-- ------------------------------------------------------------------ fixtures (as the database owner)
insert into auth.users (id, email) values
    ('00000000-0000-0000-0000-00000000000a', 'alice'), ('00000000-0000-0000-0000-00000000000b', 'bob'),
    ('00000000-0000-0000-0000-00000000000c', 'carol'), ('00000000-0000-0000-0000-00000000000d', 'dave');

create table t_vals (name text primary key, val text);
grant select, insert, update on t_vals to authenticated;

insert into public.user_groups (leader_id, name) values ('00000000-0000-0000-0000-00000000000a', 'A');
insert into public.user_groups (leader_id, name) values ('00000000-0000-0000-0000-00000000000c', 'B');
insert into t_vals select 'A', id::text from public.user_groups where name = 'A';
insert into t_vals select 'B', id::text from public.user_groups where name = 'B';
insert into public.group_members (group_id, user_id) values
    ((select id from public.user_groups where name = 'A'), '00000000-0000-0000-0000-00000000000b'),
    ((select id from public.user_groups where name = 'A'), '00000000-0000-0000-0000-00000000000d'),
    ((select id from public.user_groups where name = 'B'), '00000000-0000-0000-0000-00000000000d');

create function t_login(who text) returns void language sql as $$
    select set_config('request.jwt.claim.sub', (select id::text from auth.users where email = who), false);
$$;
create function t_put(k text, v text) returns void language sql as $$
    insert into t_vals values (k, v) on conflict (name) do update set val = excluded.val;
$$;
create function t_get(k text) returns text language sql stable as $$ select val from t_vals where name = k; $$;
create function t_assert(ok boolean, msg text) returns void language plpgsql as $$
begin
    if ok is not true then raise exception 'ASSERTION FAILED: %', msg; end if;
end;
$$;
-- Run a statement as the current role and require it to fail with an error containing `fragment`.
create function t_expect_error(stmt text, fragment text) returns void language plpgsql as $$
begin
    begin
        execute stmt;
    exception when others then
        if position(fragment in sqlerrm) = 0 then
            raise exception 'ASSERTION FAILED: % failed with "%" instead of "%"', stmt, sqlerrm, fragment;
        end if;
        return;
    end;
    raise exception 'ASSERTION FAILED: % should have failed with "%"', stmt, fragment;
end;
$$;
create function t_group(name text) returns jsonb language sql immutable as $$
    select jsonb_build_object('schema', 'angstrom.group/1', 'name', name, 'lineage_version', 2,
                              'members', '[]'::jsonb, 'conditions', '[]'::jsonb, 'score', null);
$$;
-- A Set body embedding the stored snapshot of a source version (built with owner rights, like a client that had
-- read the source; the server re-checks everything). `forged` replaces the snapshot/provenance hash.
create function t_set(name text, src text, ver integer, alter_snapshot boolean default false) returns jsonb
language sql security definer as $$
    select jsonb_build_object('schema', 'angstrom.set/1', 'name', name, 'lineage_version', 2, 'score', null,
        'standalone', '[]'::jsonb, 'market_context', '[]'::jsonb,
        'groups', jsonb_build_array(jsonb_build_object('key', 'g',
            'provenance', jsonb_build_object('source_config', src, 'source_version', ver, 'content_sha256', 'forged-by-client',
                                             'audience_ceiling', jsonb_build_object('public', true)),
            'snapshot', case when alter_snapshot then jsonb_set(v.body, '{name}', '"changed"') else v.body end)))
    from public.analysis_config_versions v
    join public.analysis_configs c on c.id = v.config_id
    where v.version = ver and (c.id::text = src or c.starter_alias = src);
$$;
grant execute on function t_login(text), t_put(text, text), t_get(text), t_assert(boolean, text),
    t_expect_error(text, text), t_group(text), t_set(text, text, integer, boolean) to authenticated, anon;

-- ------------------------------------------------------------------ 1. direct writes refused; anon refused
select t_login('alice');
set role authenticated;
select t_expect_error($$insert into public.analysis_configs (kind, owner_id, name) values ('group', auth.uid(), 'x')$$, 'permission denied');
select t_expect_error($$update public.analysis_configs set archived = true$$, 'permission denied');
select t_expect_error($$delete from public.analysis_config_versions$$, 'permission denied');
select t_expect_error($$insert into public.analysis_version_publications values (gen_random_uuid(), 1, 'public')$$, 'permission denied');
reset role;
set role anon;
select t_expect_error($$select public.analysis_create_config('group', t_group('x'))$$, 'permission denied');
select t_expect_error($$select * from public.analysis_configs$$, 'permission denied');
reset role;

-- ------------------------------------------------------------------ 2. private by default; per-version publication
select t_login('alice');
set role authenticated;
select t_put('g1', public.analysis_create_config('group', t_group('G1'))::text);
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('g1')::uuid) = 1, 'owner reads own version');
select t_assert((select content_sha256 from public.analysis_config_versions where config_id = t_get('g1')::uuid) ~ '^[0-9a-f]{64}$', 'server hash');
reset role;
select t_login('bob');
set role authenticated;
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('g1')::uuid) = 0, 'private v1 unreadable to bob');
select t_assert((select count(*) from public.analysis_configs where id = t_get('g1')::uuid) = 0, 'private config row hidden');
select t_expect_error(format($$select public.analysis_save_version(%L, 1, t_group('hijack'))$$, t_get('g1')), 'not_owner');
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'public')$$, t_get('g1')), 'not_owner');
select t_expect_error(format($$select public.analysis_archive_config(%L)$$, t_get('g1')), 'not_owner');
reset role;
select t_login('alice');
set role authenticated;
select t_assert(public.analysis_save_version(t_get('g1')::uuid, 1, t_group('G1 v2')) = 2, 'save v2');
select public.analysis_publish_version(t_get('g1')::uuid, 2, 'public');
reset role;
select t_login('bob');
set role authenticated;
select t_assert((select array_agg(version) from public.analysis_config_versions where config_id = t_get('g1')::uuid) = array[2],
                'only published v2 readable; v1 stays private');
reset role;

-- ------------------------------------------------------------------ 3. concurrent saves; immutability
select t_login('alice');
set role authenticated;
select t_expect_error(format($$select public.analysis_save_version(%L, 1, t_group('stale'))$$, t_get('g1')), 'conflict');
select t_expect_error($$update public.analysis_config_versions set body = '{}'$$, 'permission denied');
reset role;
select t_expect_error($$update public.analysis_config_versions set change_note = 'x'$$, 'immutable');

-- ------------------------------------------------------------------ 4. private at capture stays owner-only (strict)
select t_login('alice');
set role authenticated;
select t_put('gp', public.analysis_create_config('group', t_group('Private G'))::text);
select t_put('sp', public.analysis_create_config('set', t_set('S private', t_get('gp'), 1))::text);
select t_assert((select capture_ceiling from public.analysis_config_versions where config_id = t_get('sp')::uuid and version = 1)
                = '{"owner": true}'::jsonb, 'set v1 captured an owner-only group');
select public.analysis_publish_version(t_get('gp')::uuid, 1, 'public');
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'public')$$, t_get('sp')), 'beyond_capture_ceiling');
select t_assert(public.analysis_save_version(t_get('sp')::uuid, 1, t_set('S private', t_get('gp'), 1)) = 2, 're-capture in v2');
select t_assert((select capture_ceiling from public.analysis_config_versions where config_id = t_get('sp')::uuid and version = 2)
                = '{"public": true}'::jsonb, 'v2 captured the now-public group');
select public.analysis_publish_version(t_get('sp')::uuid, 2, 'public');
reset role;

-- ------------------------------------------------------------------ 5. cross-community redistribution refused
select t_login('alice');
set role authenticated;
select t_put('ga', public.analysis_create_config('group', t_group('A only'))::text);
select public.analysis_publish_version(t_get('ga')::uuid, 1, 'communities', array[t_get('A')::bigint]);
reset role;
select t_login('dave');
set role authenticated;
select t_put('sd', public.analysis_create_config('set', t_set('Dave set', t_get('ga'), 1))::text);
select t_assert((select capture_ceiling from public.analysis_config_versions where config_id = t_get('sd')::uuid)
                = jsonb_build_object('communities', jsonb_build_array(t_get('A')::bigint)), 'captured A');
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'communities', array[%s::bigint])$$, t_get('sd'), t_get('B')),
                      'beyond_capture_ceiling');
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'public')$$, t_get('sd')), 'beyond_capture_ceiling');
select public.analysis_publish_version(t_get('sd')::uuid, 1, 'communities', array[t_get('A')::bigint]);
reset role;
select t_login('bob');
set role authenticated;
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'communities', array[%s::bigint])$$, t_get('sd'), t_get('A')),
                      'not_owner');
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('sd')::uuid) = 1, 'bob (A) reads dave''s A set');
reset role;
select t_login('carol');
set role authenticated;
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('sd')::uuid) = 0, 'carol (B) cannot');
-- a non-member cannot capture an A-only group
select t_expect_error(format($$select public.analysis_create_config('set', t_set('Carol set', %L, 1))$$, t_get('ga')),
                      'not_authorised_to_capture');
-- another owner's unpublished group cannot be captured
select t_put('gc', public.analysis_create_config('group', t_group('Carol private'))::text);
reset role;
select t_login('bob');
set role authenticated;
select t_expect_error(format($$select public.analysis_create_config('set', t_set('Bob set', %L, 1))$$, t_get('gc')),
                      'not_authorised_to_capture');
-- a user cannot share to a community they are not in
select t_put('gb', public.analysis_create_config('group', t_group('Bob G'))::text);
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'communities', array[%s::bigint])$$, t_get('gb'), t_get('B')),
                      'not_in_community');
reset role;

-- ------------------------------------------------------------------ 6. within the source's own audience
select t_login('alice');
set role authenticated;
reset role;
-- alice is not in B, so give alice B membership for this scenario
insert into public.group_members (group_id, user_id) values (t_get('B')::bigint, '00000000-0000-0000-0000-00000000000a');
select t_login('alice');
set role authenticated;
select t_put('gab', public.analysis_create_config('group', t_group('A and B'))::text);
select public.analysis_publish_version(t_get('gab')::uuid, 1, 'communities', array[t_get('A')::bigint, t_get('B')::bigint]);
reset role;
select t_login('dave');
set role authenticated;
select t_put('sab', public.analysis_create_config('set', t_set('Dave AB', t_get('gab'), 1))::text);
select public.analysis_publish_version(t_get('sab')::uuid, 1, 'communities', array[t_get('A')::bigint, t_get('B')::bigint]);
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'public')$$, t_get('sab')), 'beyond_capture_ceiling');
reset role;

-- ------------------------------------------------------------------ 7. narrowing a source blocks later widening
select t_login('alice');
set role authenticated;
select t_put('gn', public.analysis_create_config('group', t_group('Narrowed'))::text);
select public.analysis_publish_version(t_get('gn')::uuid, 1, 'public');
reset role;
select t_login('dave');
set role authenticated;
select t_put('sn', public.analysis_create_config('set', t_set('Dave N', t_get('gn'), 1))::text);
reset role;
select t_login('alice');
set role authenticated;
select public.analysis_publish_version(t_get('gn')::uuid, 1, 'communities', array[t_get('A')::bigint]);
reset role;
select t_login('dave');
set role authenticated;
select t_expect_error(format($$select public.analysis_publish_version(%L, 1, 'public')$$, t_get('sn')), 'beyond_source_audience');
select public.analysis_publish_version(t_get('sn')::uuid, 1, 'communities', array[t_get('A')::bigint]);
reset role;

-- ------------------------------------------------------------------ 8. forged snapshot and provenance
select t_login('dave');
set role authenticated;
select t_expect_error(format($$select public.analysis_create_config('set', t_set('Forged', %L, 1, true))$$, t_get('gab')),
                      'snapshot_mismatch');
select t_assert((select body #>> '{groups,0,provenance,content_sha256}' from public.analysis_config_versions
                 where config_id = t_get('sab')::uuid)
                = (select content_sha256 from public.analysis_config_versions where config_id = t_get('gab')::uuid and version = 1),
                'server replaced the client hash with the source hash');
select t_assert((select body #>> '{groups,0,provenance,computed_by}' from public.analysis_config_versions
                 where config_id = t_get('sab')::uuid) = 'server', 'provenance written by the server');
reset role;

-- ------------------------------------------------------------------ 9. copies keep their copy ceiling
select t_login('bob');
set role authenticated;
select t_put('cb', public.analysis_copy_config(t_get('ga')::uuid, 1, 'Bob copy')::text);
select t_assert((select copy_ceiling from public.analysis_configs where id = t_get('cb')::uuid)
                = jsonb_build_object('communities', jsonb_build_array(t_get('A')::bigint)), 'copy ceiling A');
select t_assert(public.analysis_save_version(t_get('cb')::uuid, 1, t_group('Bob copy v2')) = 2, 'copy v2');
select t_expect_error(format($$select public.analysis_publish_version(%L, 2, 'public')$$, t_get('cb')), 'beyond_capture_ceiling');
select public.analysis_publish_version(t_get('cb')::uuid, 2, 'communities', array[t_get('A')::bigint]);
reset role;
select t_login('carol');
set role authenticated;
select t_expect_error(format($$select public.analysis_copy_config(%L, 1)$$, t_get('ga')), 'not_authorised_to_copy');
reset role;

-- ------------------------------------------------------------------ 10. leaving a community ends access
delete from public.group_members where user_id = '00000000-0000-0000-0000-00000000000b' and group_id = t_get('A')::bigint;
select t_login('bob');
set role authenticated;
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('sd')::uuid) = 0, 'bob left A');
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('cb')::uuid) = 2,
                'bob keeps his own copy');
reset role;

-- ------------------------------------------------------------------ 11. starters: service role only; public; embeddable
select t_login('alice');
set role authenticated;
select t_expect_error($$select public.analysis_seed_starter('starter:x', t_group('X'))$$, 'permission denied');
reset role;
set role service_role;
select public.analysis_seed_starter('starter:trend-confirmation', t_group('Trend Confirmation'));
select public.analysis_seed_starter('starter:trend-confirmation', t_group('Trend Confirmation'));  -- unchanged: no new version
reset role;
select t_assert((select current_version from public.analysis_configs where starter_alias = 'starter:trend-confirmation') = 1,
                'reseeding an unchanged starter adds no version');
select t_login('carol');
set role authenticated;
select t_assert((select count(*) from public.analysis_config_versions v join public.analysis_configs c on c.id = v.config_id
                 where c.starter_alias = 'starter:trend-confirmation') = 1, 'everyone reads starters');
select t_put('ss', public.analysis_create_config('set', t_set('Carol starter set', 'starter:trend-confirmation', 1))::text);
select public.analysis_publish_version(t_get('ss')::uuid, 1, 'public');
reset role;

-- ------------------------------------------------------------------ 12. archive
select t_login('alice');
set role authenticated;
select public.analysis_archive_config(t_get('g1')::uuid);
select t_expect_error(format($$select public.analysis_save_version(%L, 2, t_group('after archive'))$$, t_get('g1')), 'archived');
reset role;
select t_login('bob');
set role authenticated;
select t_assert((select count(*) from public.analysis_config_versions where config_id = t_get('g1')::uuid) = 1,
                'archived versions stay readable where published (pins and copies stay valid)');
reset role;

-- ------------------------------------------------------------------ 13. publication log is owner-only
select t_login('carol');
set role authenticated;
select t_assert((select count(*) from public.analysis_publication_log where config_id = t_get('g1')::uuid) = 0, 'log owner-only');
reset role;
select t_login('alice');
set role authenticated;
select t_assert((select count(*) from public.analysis_publication_log where config_id = t_get('g1')::uuid) >= 3, 'owner sees log');
reset role;

\echo ALL SIGNAL GROUP SECURITY TESTS PASSED

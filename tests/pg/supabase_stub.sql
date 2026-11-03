-- The parts of Supabase that sql/2026-11-04_signal_groups.sql relies on, for tests on a plain Postgres:
-- the anon / authenticated / service_role roles, auth.users, auth.uid() (read from the request's JWT subject),
-- and the existing community tables (same columns as production).

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end
$$;

create schema if not exists auth;
create table if not exists auth.users (id uuid primary key, email text);

create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;

create table if not exists public.user_groups (
    id bigint generated always as identity primary key,
    leader_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.group_members (
    group_id bigint not null references public.user_groups (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    joined_at timestamptz not null default now(),
    primary key (group_id, user_id)
);

-- "What followed" studies of people's own Sets (design: docs/research/what_followed_brief_2026-11-08.md).
-- Safe to run more than once. Adds one table and one function; nothing existing changes.
--
-- One row per Set logic (a fingerprint of what the Set checks, ignoring its name), shared like set_history: the
-- study describes public price history, so two accounts with the same Set share one study. Tapping "Study this Set"
-- queues it; a GitHub job (set-studies.yml) picks queued rows every half hour, works out the study on the saved
-- prices before the protected hold-out (30 Oct 2024) and writes the result. Only that job (service role) writes
-- status and results.

create table if not exists public.set_studies (
    set_hash text primary key check (char_length(set_hash) between 8 and 64),
    set_body jsonb not null check (octet_length(set_body::text) < 200000),
    set_name text not null default '' check (char_length(set_name) <= 200),
    status text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed', 'refused')),
    requested_by uuid references auth.users (id) on delete set null,
    requested_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz,
    method text,
    result jsonb,
    error text check (error is null or char_length(error) <= 500)
);

create index if not exists set_studies_queue on public.set_studies (status, requested_at);

alter table public.set_studies enable row level security;
revoke all on public.set_studies from public, anon;
grant select on public.set_studies to authenticated;

drop policy if exists "signed-in accounts read set studies" on public.set_studies;
create policy "signed-in accounts read set studies" on public.set_studies
    for select to authenticated using (true);

-- Queue a study. Returns the row's status after the call. A Set already queued, running or done is not queued again;
-- a failed one is queued again. At most 5 waiting studies per account.
create or replace function public.request_set_study(set_hash text, body jsonb, name text)
returns text
language plpgsql
security definer
set search_path = public
as $$
#variable_conflict use_column
declare
    me uuid := auth.uid();
    current_status text;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    select s.status into current_status from public.set_studies s where s.set_hash = request_set_study.set_hash;
    if current_status in ('queued', 'running', 'done', 'refused') then
        return current_status;
    end if;
    if (select count(*) from public.set_studies s
         where s.requested_by = me and s.status in ('queued', 'running')) >= 5 then
        raise exception 'too_many_waiting';
    end if;
    insert into public.set_studies as s (set_hash, set_body, set_name, status, requested_by, requested_at,
                                         started_at, finished_at, result, error)
    values (request_set_study.set_hash, body, left(coalesce(name, ''), 200), 'queued', me, now(), null, null, null,
            null)
    on conflict (set_hash) do update
        set set_body = excluded.set_body, set_name = excluded.set_name, status = 'queued',
            requested_by = me, requested_at = now(), started_at = null, finished_at = null, result = null,
            error = null
        where s.status = 'failed';
    return 'queued';
end;
$$;

revoke all on function public.request_set_study(text, jsonb, text) from public, anon;
grant execute on function public.request_set_study(text, jsonb, text) to authenticated;

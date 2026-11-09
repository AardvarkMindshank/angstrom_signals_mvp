-- Fix: "Study this Set" failed with "column reference set_hash is ambiguous" (the function's input and the table's
-- column share the name, and the insert's ON CONFLICT (set_hash) could mean either). Same function, with Postgres told
-- to read such names as the column; the input is always written request_set_study.set_hash. Safe to run more than once.

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

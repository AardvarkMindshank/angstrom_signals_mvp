-- Undo for deleting a Group or Set in Angstrom Lattice. Deleting archives (hides) it; this brings it back.
-- Safe to run more than once. Adds one function; nothing existing changes.

create or replace function public.analysis_restore_config(cfg uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
begin
    update public.analysis_configs set archived = false, updated_at = now()
     where id = cfg and owner_id = me and me is not null and archived;
    if not found then raise exception 'not_owner'; end if;
    insert into public.analysis_publication_log (config_id, action, actor) values (cfg, 'restore', me);
end;
$$;

revoke all on function public.analysis_restore_config(uuid) from public, anon;
grant execute on function public.analysis_restore_config(uuid) to authenticated;

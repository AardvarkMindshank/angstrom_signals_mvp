-- Trade Log: rename a connection's tab (22 Nov 2026). Safe to run more than once. Adds one function.
-- The name is only the label on the platform's tab (handy with two accounts on one platform).

create or replace function public.tradelog_rename_connection(p_id uuid, p_label text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.trade_connections
       set label = left(btrim(coalesce(p_label, '')), 30)
     where id = p_id and user_id = auth.uid();
    return found;
end;
$$;

revoke all on function public.tradelog_rename_connection(uuid, text) from public, anon;
grant execute on function public.tradelog_rename_connection(uuid, text) to authenticated;

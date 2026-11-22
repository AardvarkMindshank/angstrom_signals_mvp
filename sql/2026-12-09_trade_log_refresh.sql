-- Trade Log Refresh button (22 Nov 2026). Safe to run more than once. Adds one column and one function.
-- A member's Refresh asks the background worker to sync that connection on its next pass (within about 5 minutes).
-- At most one request every 10 minutes per connection.

alter table public.trade_connections add column if not exists refresh_requested_at timestamptz;

create or replace function public.tradelog_request_refresh(p_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.trade_connections
       set refresh_requested_at = now()
     where id = p_id
       and user_id = auth.uid()
       and status <> 'paused'
       and (refresh_requested_at is null or refresh_requested_at < now() - interval '10 minutes')
       and (last_sync_at is null or last_sync_at < now() - interval '10 minutes');
    return found;
end;
$$;

revoke all on function public.tradelog_request_refresh(uuid) from public, anon;
grant execute on function public.tradelog_request_refresh(uuid) to authenticated;

-- 📱 Phone and desktop notifications (14 Nov 2026): the installable web app can show each new notification as a push.
-- push_subscriptions holds one row per device someone turned notifications on for (Settings → Notifications). The
-- alert worker sends every new notification to that person's devices and marks it pushed (user_notifications.pushed_at).
-- A device that has gone away (the browser says so) is removed by the worker.
--
-- Safe to run more than once. Adds one table, one column and two functions; changes nothing else.

create table if not exists public.push_subscriptions (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    endpoint text not null unique check (char_length(endpoint) between 10 and 1000),
    p256dh text not null check (char_length(p256dh) <= 200),
    auth text not null check (char_length(auth) <= 100),
    device text not null default '' check (char_length(device) <= 60),
    created_at timestamptz not null default now(),
    last_ok_at timestamptz
);

create index if not exists push_subscriptions_user on public.push_subscriptions (user_id);

alter table public.push_subscriptions enable row level security;

drop policy if exists "own push subscriptions" on public.push_subscriptions;
create policy "own push subscriptions" on public.push_subscriptions
    for select
    to authenticated
    using (auth.uid() = user_id);

grant select on public.push_subscriptions to authenticated;

-- Turn notifications on for this device. A device someone else used before is handed over to this account.
create or replace function public.push_subscribe(p_endpoint text, p_p256dh text, p_auth text, p_device text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'not signed in';
    end if;
    if p_endpoint is null or p_endpoint !~ '^https://' then
        raise exception 'not a push address';
    end if;
    delete from public.push_subscriptions where endpoint = p_endpoint;
    insert into public.push_subscriptions (user_id, endpoint, p256dh, auth, device)
    values (auth.uid(), p_endpoint, left(coalesce(p_p256dh, ''), 200), left(coalesce(p_auth, ''), 100),
            left(coalesce(p_device, ''), 60));
end;
$$;

-- Turn them off for this device.
create or replace function public.push_unsubscribe(p_endpoint text)
returns void
language sql
security definer
set search_path = public
as $$
    delete from public.push_subscriptions where endpoint = p_endpoint and user_id = auth.uid();
$$;

revoke all on function public.push_subscribe(text, text, text, text) from public;
revoke all on function public.push_subscribe(text, text, text, text) from anon;
grant execute on function public.push_subscribe(text, text, text, text) to authenticated;
revoke all on function public.push_unsubscribe(text) from public;
revoke all on function public.push_unsubscribe(text) from anon;
grant execute on function public.push_unsubscribe(text) to authenticated;

-- Which notifications have been sent as a push (so each goes once).
alter table public.user_notifications add column if not exists pushed_at timestamptz;

create index if not exists user_notifications_unpushed
    on public.user_notifications (created_at)
    where pushed_at is null;

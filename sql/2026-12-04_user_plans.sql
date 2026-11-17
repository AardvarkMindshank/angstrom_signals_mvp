-- 18 Nov 2026: each account's membership plan (Free, Plus, Pro, Elite).
-- The owner can read their own plan; only the server (service role, later fed by Paddle) can set it.
-- No row means the beta default, Pro, decided in plans.py. Safe to run more than once.

create table if not exists public.user_plans (
    user_id uuid primary key references auth.users (id) on delete cascade,
    plan text not null default 'pro' check (plan in ('free', 'plus', 'pro', 'elite')),
    source text,                      -- 'beta', 'paddle', 'admin'
    renews_at timestamptz,
    updated_at timestamptz not null default now()
);

alter table public.user_plans enable row level security;

drop policy if exists "read own plan" on public.user_plans;
create policy "read own plan" on public.user_plans
    for select
    to authenticated
    using (user_id = auth.uid());

revoke insert, update, delete on public.user_plans from anon, authenticated;
grant select on public.user_plans to authenticated;
grant all on public.user_plans to service_role;

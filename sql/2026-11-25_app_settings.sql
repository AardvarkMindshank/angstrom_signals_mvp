-- App-wide settings that are the same for everyone, chosen by an admin (ai_providers.py). The first one: which AI
-- scores the shared news sentiment (row key "ai", value {"sentiment": "grok" | "claude" | "chatgpt" | "gemini"}).
-- Safe to run more than once. Adds one table and one function; changes nothing else.
-- Anyone can read the settings (they hold no secrets: only which AI is used); only an admin can change them.

create table if not exists public.app_settings (
    key text primary key,
    value jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    updated_by uuid references auth.users (id) on delete set null
);

alter table public.app_settings enable row level security;

drop policy if exists "read app settings" on public.app_settings;
create policy "read app settings" on public.app_settings
    for select
    to anon, authenticated
    using (true);

grant select on public.app_settings to anon, authenticated;

-- Admins change a setting through this function (it merges the change into what is there).
create or replace function public.app_setting_set(p_key text, p_patch jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    insert into public.app_settings (key, value, updated_at, updated_by)
    values (p_key, coalesce(p_patch, '{}'::jsonb), now(), auth.uid())
    on conflict (key) do update
        set value = public.app_settings.value || coalesce(excluded.value, '{}'::jsonb),
            updated_at = now(),
            updated_by = auth.uid();
end;
$$;

revoke all on function public.app_setting_set(text, jsonb) from public;
revoke all on function public.app_setting_set(text, jsonb) from anon;
grant execute on function public.app_setting_set(text, jsonb) to authenticated;

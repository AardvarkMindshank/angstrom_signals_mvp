-- A Set's answer on every past day, kept as spans for the coloured bands and the Visualize History strip
-- (design: docs/design/set_history.md). Safe to run more than once. Adds one table; nothing existing changes.
--
-- One row per Set definition (a hash of its content, so accounts that use the same Set share it) and asset:
-- [[first day, last day, answer], ...]. Ten years of days are a few kilobytes. Only new days are worked out after
-- the first time.

create table if not exists public.set_history (
    def_hash text not null check (char_length(def_hash) between 8 and 64),
    asset_key text not null check (char_length(asset_key) between 3 and 80),   -- "crypto:bitcoin", "equity:AAPL"
    through date not null,                                                   -- the last day worked out
    spans jsonb not null,
    computed_at timestamptz not null default now(),
    primary key (def_hash, asset_key)
);

alter table public.set_history enable row level security;
revoke all on public.set_history from public, anon;
grant select, insert, update on public.set_history to authenticated;

drop policy if exists "signed-in accounts read set history" on public.set_history;
create policy "signed-in accounts read set history" on public.set_history
    for select to authenticated using (true);

-- Signed-in accounts may save what they worked out (a shared cache of answers to public price history).
drop policy if exists "signed-in accounts save set history" on public.set_history;
create policy "signed-in accounts save set history" on public.set_history
    for insert to authenticated with check (true);
drop policy if exists "signed-in accounts update set history" on public.set_history;
create policy "signed-in accounts update set history" on public.set_history
    for update to authenticated using (true) with check (true);

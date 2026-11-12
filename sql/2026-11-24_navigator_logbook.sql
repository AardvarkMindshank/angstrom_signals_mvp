-- The AI Navigator's logbook: Today's AI Passage Plan, one per person per day, kept with the readings it used so it
-- can be read again and graded later (navigator.py). Safe to run more than once. Adds one table; changes nothing else.
-- Each account sees and writes only its own entries.

create table if not exists public.navigator_logbook (
    id bigserial primary key,
    owner_id uuid not null references auth.users (id) on delete cascade,
    kind text not null,                      -- passage_plan (later: event notes)
    day date not null,
    body text not null,                      -- what the Navigator wrote
    readings jsonb,                          -- the Tides readings it used (time, tide, sea, winds)
    model text,
    created_at timestamptz not null default now()
);

create index if not exists navigator_logbook_owner_day on public.navigator_logbook (owner_id, kind, day desc);

alter table public.navigator_logbook enable row level security;

drop policy if exists "own logbook" on public.navigator_logbook;
create policy "own logbook" on public.navigator_logbook
    for all
    to authenticated
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

grant select, insert, update, delete on public.navigator_logbook to authenticated;
grant usage, select on sequence public.navigator_logbook_id_seq to authenticated;

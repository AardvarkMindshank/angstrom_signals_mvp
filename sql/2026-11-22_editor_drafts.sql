-- Unsaved changes in the Group, Set and funnel editors, kept per account so they survive closing the browser
-- (drafts.py). Safe to run more than once. Adds one table; changes nothing else.
-- Each account sees and changes only its own drafts.

create table if not exists public.editor_drafts (
    owner_id uuid not null references auth.users (id) on delete cascade,
    kind text not null check (kind in ('group', 'set', 'funnel')),
    draft_key text not null,                 -- which Group, Set or funnel the editor had open
    body jsonb not null,                     -- the working copy
    updated_at timestamptz not null default now(),
    primary key (owner_id, kind, draft_key)
);

alter table public.editor_drafts enable row level security;

drop policy if exists "own drafts" on public.editor_drafts;
create policy "own drafts" on public.editor_drafts
    for all
    to authenticated
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

grant select, insert, update, delete on public.editor_drafts to authenticated;

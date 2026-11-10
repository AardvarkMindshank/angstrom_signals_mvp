-- Shared Set answers for funnels (docs/design/funnels_v2_spec.md, part 1). Safe to run more than once.
-- One row per (Set logic, certified code, asset, close): every funnel that checks the same Set logic at the same close
-- reads it instead of working it out again. Written and read only by the funnel job (service role); no account reads it.

create table if not exists public.set_answers (
    logic_hash text not null check (char_length(logic_hash) between 8 and 64),
    code_id text not null check (char_length(code_id) between 6 and 64),
    asset_key text not null check (char_length(asset_key) between 3 and 140),
    cutoff timestamptz not null,
    answer text not null check (answer in ('yes', 'no', 'unknown')),
    reason text check (reason is null or char_length(reason) <= 500),
    created_at timestamptz not null default now(),
    primary key (logic_hash, code_id, asset_key, cutoff)
);

create index if not exists set_answers_created on public.set_answers (created_at);

alter table public.set_answers enable row level security;
revoke all on public.set_answers from anon, authenticated;

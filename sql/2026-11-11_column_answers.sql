-- Answers for table columns that read 4-hour, hourly or weekly candles (design: docs/design/table_columns.md).
-- Safe to run more than once. Adds one table; nothing existing changes.
--
-- The background worker works these columns out at each close of their shortest timeframe and keeps only the
-- latest answer per definition and asset (a few hundred bytes), so the tables never need to store or download
-- intraday candles. A definition is identified by a hash of its content, so accounts that chose the same Group or
-- Set share one answer.

create table if not exists public.column_answers (
    def_hash text not null check (char_length(def_hash) between 8 and 64),
    asset_key text not null check (char_length(asset_key) between 3 and 80),   -- "crypto:bitcoin", "equity:AAPL"
    cutoff timestamptz not null,                                             -- the answer is "as of" this moment
    payload jsonb not null,                                                  -- score, label or answer, and why
    computed_at timestamptz not null default now(),
    primary key (def_hash, asset_key)
);

alter table public.column_answers enable row level security;
revoke all on public.column_answers from public, anon;
grant select on public.column_answers to authenticated;

drop policy if exists "signed-in accounts read column answers" on public.column_answers;
create policy "signed-in accounts read column answers" on public.column_answers
    for select to authenticated using (true);

-- Sentiment history: record when the database actually received each observation.
-- Safe to run more than once. Adds one column; changes no existing value except filling the new column.
--
-- recorded_at is the time the app says the score was produced. The writing function accepts times up to 30 days
-- in the past, so recorded_at alone does not prove a score was available then. first_seen_at is set by the
-- database on insert and cannot be supplied by the caller. Rows that existed before this column are stamped with
-- the time this file is run (conservative: they count as available only from then).
-- Point-in-time replays of the sentiment signals use first_seen_at (docs/design/library_completion.md, section 9).

alter table public.sentiment_history
    add column if not exists first_seen_at timestamptz not null default now();

-- The column is read by signed-in users like the rest of the table (existing select policy and grant).

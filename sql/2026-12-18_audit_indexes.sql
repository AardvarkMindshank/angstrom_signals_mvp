-- Audit (28 Nov 2026): indexes for the reads the app and the background worker make most often. Each lets the
-- database go straight to the rows asked for instead of reading the whole table. With today's handful of members the
-- gain is small; it keeps pages and the 5-minute worker quick as members and history grow. Safe to run more than once.

-- The bell's unread count (every page change and every 5 minutes) and the Alerts list.
create index if not exists user_notifications_user_created on public.user_notifications (user_id, created_at desc);
create index if not exists user_notifications_user_unread on public.user_notifications (user_id) where is_read = false;

-- Trade Log: the worker's per-member counts and its per-connection reads.
create index if not exists trade_snapshots_user on public.trade_snapshots (user_id);
create index if not exists trade_round_trips_connection on public.trade_round_trips (connection_id, copied);

-- The worker's "not emailed yet" checks every 5 minutes (feedback, reports, invites).
create index if not exists feedback_notes_not_emailed on public.feedback_notes (created_at) where emailed_at is null;
create index if not exists comment_reports_not_emailed on public.comment_reports (created_at) where emailed_at is null;
create index if not exists invites_not_emailed on public.invites (created_at) where emailed_at is null;

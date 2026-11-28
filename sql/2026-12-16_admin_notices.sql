-- New feedback and comment reports are emailed to the admins by the background worker (beta_worker.py), whichever
-- app they came from. The worker marks each one emailed, so it goes once. Safe to run more than once.

alter table public.feedback_notes add column if not exists emailed_at timestamptz;
alter table public.comment_reports add column if not exists emailed_at timestamptz;

-- Everything sent before today was already emailed by the classic app.
update public.feedback_notes set emailed_at = coalesce(created_at, now()) where emailed_at is null;
update public.comment_reports set emailed_at = coalesce(created_at, now()) where emailed_at is null;

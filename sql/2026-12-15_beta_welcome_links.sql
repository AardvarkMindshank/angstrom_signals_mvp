-- Welcome and barred emails sent by the background worker (beta_worker.py), whichever app or link made the decision.
-- An approved email gets a welcome with its own "set your password" link; a barred email gets the barred note.
-- The worker marks each one sent, so it goes once. Safe to run more than once.

alter table public.beta_access add column if not exists welcomed_at timestamptz;
alter table public.email_blacklist add column if not exists notified_at timestamptz;

-- Everyone approved or barred before today was already emailed by the app that made the decision.
update public.beta_access set welcomed_at = coalesce(created_at, now()) where welcomed_at is null;
update public.email_blacklist set notified_at = coalesce(created_at, now()) where notified_at is null;

-- The closed-beta message someone sees if they try to sign up without a seat (the old wording named the old brand).
create or replace function public.beta_gate()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if public.signup_is_open() then
        return new;
    end if;
    if exists (
        select 1 from public.beta_access
        where email = lower(btrim(coalesce(new.email, '')))
    ) then
        return new;
    end if;
    raise exception 'MarketNavi is in closed beta. Request access at marketnavi.ai/beta.html.';
end;
$$;

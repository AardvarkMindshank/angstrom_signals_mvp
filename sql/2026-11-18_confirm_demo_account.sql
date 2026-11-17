-- Confirm the demo account's email by hand (18 Nov 2026).
-- Use when the sign-up confirmation email never arrived (the built-in Supabase mail sender only sends a few emails
-- an hour, and they often land in spam). Safe to run more than once. Change the address on the two lines marked
-- <-- if the demo account uses a different email.

-- 1. Confirm the email, so the account can log in.
update auth.users
set email_confirmed_at = coalesce(email_confirmed_at, now())
where lower(email) = 'demo@angstromsignals.com';                              -- <--

-- 2. Show where things stand. One row for the account and whether it is approved for the beta.
select u.email,
       u.created_at as account_created,
       u.email_confirmed_at as email_confirmed,
       exists (select 1 from public.beta_access b where b.email = lower(u.email)) as approved_for_beta
from auth.users as u
where lower(u.email) = 'demo@angstromsignals.com';                            -- <--

# Sign-up and sign-in emails (Supabase Auth through Resend)

Supabase sends the account emails (confirm sign-up, reset password, sign-in link, email change, invite). Out of the
box it uses its own test mail server, which sends only a few emails an hour and often lands in junk. These templates
and the steps below send them through Resend, from the angstromsignals.com domain the alert emails already use.

## 1 and 2. Resend and Supabase SMTP: already done
Custom SMTP is on: sender noreply@angstromsignals.com ("Angstrom Signals"), host smtp.resend.com, port 465, user
resend. If emails stop arriving, Resend's Emails page shows each one sent and whether it was delivered.

## 3. Supabase: Authentication → Rate Limits
Raise **Rate limit for sending emails** to 30 an hour (or more); with custom SMTP it is no longer capped at 2.

## 4. Supabase: Authentication → Emails → Templates
For each template, set the Subject and paste the matching file's whole contents into the message body:

| Template | Subject | File |
|---|---|---|
| Confirm signup | Confirm your email for Angstrom Signals | confirm_signup.html |
| Reset Password | Reset your Angstrom Signals password | reset_password.html |
| Magic Link | Your Angstrom Signals sign-in link | magic_link.html |
| Change Email Address | Confirm your new email for Angstrom Signals | change_email.html |
| Invite user | You're invited to Angstrom Signals | invite.html |

## 5. Test
Sign up with a fresh address (an @angstromsignals.com mailbox works) after approving it in Admin › Beta requests,
and check the confirmation email arrives within a minute, from noreply@angstromsignals.com, not in junk.

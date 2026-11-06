# Beta NDA signing

Status: built 6 November 2026 (branch `beta-nda`). The owner's draft (v2, with placeholders such as the legal entity name) is installed switched off; it goes on with the final version.

## Flow

1. A person applies on the website; Drew approves (unchanged). The welcome email says they will sign the NDA at
   their first sign-in (only while the NDA is switched on).
2. They create their account (unchanged).
3. On sign-in, until they have signed the current NDA version, the dashboard shows only the NDA page: the text (also
   as a PDF download), a tick box, their typed full legal name and a drawn signature (finger or mouse).
4. Signing stores the record and a signed copy (the NDA plus a signature page), then opens the dashboard. The worker
   emails the copy to the signer and to every admin.
5. Admins never sign. A new NDA version asks everyone to sign again.

## The record

Account, email, typed name, drawn signature (PNG), server time, IP address, browser, NDA version, the PDF's SHA-256
fingerprint and a signing reference. One per account per version. Stored in `nda_signatures`, written only through
`nda_sign()`; no account can change or delete it. Signers read their own; admins read all, and the copies, through
admin functions.

## Admin

Beta requests table: a new NDA column (✍️ date signed, ⏳ waiting, ⏳ no account yet, ↻ signed an older version,
Admin, — before approval). Below it: the count of signatures, **Preview the NDA page** (nothing recorded; a sample
signed copy to download) and a picker to download any signed copy.

## Legal note

A tick, a typed name and a drawn signature, with this record, is a simple electronic signature, recognised for most
contracts in many places (for example the US ESIGN Act, the EU's eIDAS regulation, Thailand's Electronic Transactions
Act). This is not legal advice: the owner will have a lawyer review the NDA and this method before relying on it.

## Setup

`sql/2026-11-09_beta_nda.sql`, then the PDF and `legal/nda/current.json` (see legal/nda/README.md). New Python
packages: `pypdf`, `reportlab` (requirements.txt).

## CI

Run 42164380961 on commit 4d2f4fd: tests, chart (including 8 signature pad checks in a browser), overlap and
replay all passed.

-- Beta NDA signing (design: docs/design/beta_nda.md).
-- Safe to run more than once. Adds one table and four functions, and replaces admin_beta_requests() with the same
-- fields plus NDA status. Nothing is removed.
--
-- Rules enforced here, on the server:
--  * A signature is written only through nda_sign(), for the signed-in account, with the server's time. Nobody can
--    change or delete a signature afterwards (no update or delete is granted to anyone signed in).
--  * One signature per account per NDA version.
--  * Signers read their own signatures; admins read all of them, and the signed copies, through admin functions.
--  * The background worker (service role) emails the copies and records when it did.

create table if not exists public.nda_signatures (
    id bigint generated always as identity primary key,
    reference uuid not null unique,                 -- printed on the signed copy
    user_id uuid not null references auth.users (id) on delete restrict,
    email text not null,
    nda_version text not null check (char_length(nda_version) between 1 and 40),
    doc_sha256 text not null check (doc_sha256 ~ '^[0-9a-f]{64}$'),
    full_name text not null check (char_length(btrim(full_name)) between 2 and 120),
    drawing_png text not null check (char_length(drawing_png) between 100 and 400000),   -- base64 PNG
    signed_pdf text not null check (char_length(signed_pdf) <= 12000000),                 -- base64 PDF copy
    ip text check (char_length(ip) <= 100),
    user_agent text check (char_length(user_agent) <= 400),
    signed_at timestamptz not null default now(),
    emailed_at timestamptz,
    unique (user_id, nda_version)
);

alter table public.nda_signatures enable row level security;
revoke all on public.nda_signatures from public, anon, authenticated;
grant select (id, reference, nda_version, doc_sha256, full_name, signed_at) on public.nda_signatures to authenticated;

drop policy if exists "signers read their signatures" on public.nda_signatures;
create policy "signers read their signatures" on public.nda_signatures
    for select to authenticated using (user_id = auth.uid());

-- Has the signed-in account signed this version? Admins never need to.
create or replace function public.nda_status(p_version text)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
    select jsonb_build_object(
        'is_admin', coalesce(public.is_admin(), false),
        'signed', exists (select 1 from public.nda_signatures
                          where user_id = auth.uid() and nda_version = p_version),
        'signed_at', (select signed_at from public.nda_signatures
                      where user_id = auth.uid() and nda_version = p_version));
$$;

create or replace function public.nda_sign(p_reference uuid, p_version text, p_sha256 text, p_full_name text,
                                           p_drawing text, p_signed_pdf text, p_ip text, p_user_agent text)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    me uuid := auth.uid();
    my_email text;
    new_id bigint;
begin
    if me is null then raise exception 'not_signed_in'; end if;
    select lower(email) into my_email from auth.users where id = me;
    if exists (select 1 from public.nda_signatures where user_id = me and nda_version = p_version) then
        raise exception 'already_signed';
    end if;
    insert into public.nda_signatures (reference, user_id, email, nda_version, doc_sha256, full_name, drawing_png,
                                       signed_pdf, ip, user_agent)
    values (p_reference, me, coalesce(my_email, ''), p_version, lower(p_sha256), btrim(p_full_name), p_drawing,
            p_signed_pdf, left(p_ip, 100), left(p_user_agent, 400))
    returning id into new_id;
    return new_id;
end;
$$;

-- Admins: the signed copy of one signature, as base64.
create or replace function public.admin_nda_copy(p_id bigint)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then raise exception 'not allowed'; end if;
    return (select jsonb_build_object('email', email, 'full_name', full_name, 'nda_version', nda_version,
                                      'signed_at', signed_at, 'reference', reference, 'pdf', signed_pdf)
              from public.nda_signatures where id = p_id);
end;
$$;

-- The beta requests table for admins, as before, plus: does the email have an account, and its latest NDA
-- signature (version, time, id). The page compares the version with the current NDA.
create or replace function public.admin_beta_requests()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if not public.is_admin() then
        raise exception 'not allowed';
    end if;
    return coalesce(
        (
            select jsonb_agg(
                jsonb_build_object(
                    'id', r.id,
                    'created_at', r.created_at,
                    'name', r.name,
                    'email', r.email,
                    'phone', r.phone,
                    'country', r.country,
                    'markets', r.markets,
                    'years_trading', r.years_trading,
                    'activity', r.activity,
                    'tools', r.tools,
                    'why', r.why,
                    'status', r.status,
                    'has_account', u.id is not null,
                    'account_admin', coalesce(p.role = 'admin', false),
                    'nda_id', s.id,
                    'nda_version', s.nda_version,
                    'nda_signed_at', s.signed_at
                )
                order by r.created_at desc
            )
            from public.beta_requests as r
            left join auth.users as u on lower(u.email) = lower(btrim(r.email))
            left join public.profiles as p on p.user_id = u.id
            left join lateral (
                select id, nda_version, signed_at from public.nda_signatures
                 where user_id = u.id order by signed_at desc limit 1
            ) as s on true
        ),
        '[]'::jsonb
    );
end;
$$;

revoke all on function public.nda_status(text) from public, anon;
revoke all on function public.nda_sign(uuid, text, text, text, text, text, text, text) from public, anon;
revoke all on function public.admin_nda_copy(bigint) from public, anon;
grant execute on function public.nda_status(text) to authenticated;
grant execute on function public.nda_sign(uuid, text, text, text, text, text, text, text) to authenticated;
grant execute on function public.admin_nda_copy(bigint) to authenticated;

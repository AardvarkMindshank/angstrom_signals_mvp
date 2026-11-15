-- 👤 Who is an admin (15 Nov 2026). Run in Supabase → SQL Editor.
--
-- Step 1: run this part as it is. It only reads: every account, its email and its role.
-- An account is an admin when role = 'admin'; anything else (empty, 'member' …) is a normal user.

select u.email, p.role, p.display_name, u.created_at::date as joined
from auth.users u
left join public.profiles p on p.user_id = u.id
order by (p.role = 'admin') desc nulls last, u.email;

-- Step 2 (only if the Google account shows as admin): make it a normal user.
-- Put the Google account's email between the quotes, remove the two dashes at the start of the line, and run
-- just that line. It changes that one account only; your Hotmail admin account is not touched.

-- update public.profiles set role = null where user_id = (select id from auth.users where email = 'GOOGLE-EMAIL-HERE');

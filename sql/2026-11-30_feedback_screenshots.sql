-- 📝 Screenshots with feedback (15 Nov 2026). Run once in Supabase → SQL Editor. Safe to run again.
--
-- 1. A private storage bucket "feedback" for the screenshots. Private: nobody can open a picture by its address;
--    the app makes a short-lived link for the person who sent it and for admins only. Pictures only, at most 5 MB.
-- 2. Each feedback note gets a list of its pictures (images).
-- 3. The admin feedback list includes those pictures.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('feedback', 'feedback', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
    set public = false,
        file_size_limit = 5242880,
        allowed_mime_types = array['image/jpeg', 'image/png', 'image/webp'];

-- A signed-in person uploads into their own folder (feedback/<their id>/...), and can see their own pictures.
drop policy if exists "users upload own feedback images" on storage.objects;
create policy "users upload own feedback images" on storage.objects
    for insert
    to authenticated
    with check (
        bucket_id = 'feedback'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

drop policy if exists "users read own feedback images" on storage.objects;
create policy "users read own feedback images" on storage.objects
    for select
    to authenticated
    using (
        bucket_id = 'feedback'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- Admins can see every feedback picture.
drop policy if exists "admins read feedback images" on storage.objects;
create policy "admins read feedback images" on storage.objects
    for select
    to authenticated
    using (bucket_id = 'feedback' and public.is_admin());

-- The pictures of a note: their places in the bucket, at most 3.
alter table public.feedback_notes add column if not exists images text[] not null default '{}';
alter table public.feedback_notes drop constraint if exists feedback_notes_images_check;
alter table public.feedback_notes
    add constraint feedback_notes_images_check check (coalesce(array_length(images, 1), 0) <= 3);

-- The admin list, now with each note's pictures.
create or replace function public.admin_feedback()
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
    return coalesce((
        select jsonb_agg(to_jsonb(item) order by item.created_at desc)
        from (
            select
                notes.id,
                notes.kind,
                notes.body,
                notes.status,
                notes.user_email as email,
                notes.created_at,
                coalesce(notes.images, '{}') as images,
                coalesce(
                    nullif(btrim(profiles.display_name), ''),
                    nullif(split_part(notes.user_email, '@', 1), ''),
                    'Member'
                ) as username,
                coalesce(profiles.avatar_url, '') as avatar,
                coalesce((
                    select jsonb_agg(jsonb_build_object(
                        'status', events.status,
                        'note', events.note,
                        'at', events.created_at
                    ) order by events.created_at)
                    from public.feedback_events events
                    where events.feedback_id = notes.id
                ), '[]'::jsonb) as events
            from public.feedback_notes notes
            left join public.profiles profiles on profiles.user_id = notes.user_id
        ) item
    ), '[]'::jsonb);
end;
$$;

revoke all on function public.admin_feedback() from public;
revoke all on function public.admin_feedback() from anon;
grant execute on function public.admin_feedback() to authenticated;

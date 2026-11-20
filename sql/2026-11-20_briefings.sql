-- 🎧 Morning briefings (briefing.py): a public storage bucket for the episodes and private podcast feeds.
-- Files sit under a random token per member (<token>/<day>.mp3, .txt, feed.xml), so only someone with the link
-- can find them. Only the background worker (service key) writes; nobody lists the bucket.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('briefings', 'briefings', true, 10485760,
        array['audio/mpeg', 'text/plain', 'application/json', 'application/rss+xml'])
on conflict (id) do update set public = true, file_size_limit = excluded.file_size_limit,
                               allowed_mime_types = excluded.allowed_mime_types;

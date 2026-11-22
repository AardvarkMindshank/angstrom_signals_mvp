-- Trade Log weekly reviews (22 Nov 2026, spec phase 4). Safe to run more than once. Adds one table.
-- One review per member, week and scope ("all", "class:crypto", "platform:etoro"), written by the app when the
-- member first opens it, from facts about their own trades. Members read and write only their own.

create table if not exists public.trade_reviews (
    user_id uuid not null references auth.users (id) on delete cascade,
    week_start date not null,
    scope text not null default 'all' check (char_length(scope) <= 40),
    review jsonb not null check (pg_column_size(review) < 20000),
    provider text not null default '' check (char_length(provider) <= 20),
    language text not null default 'en' check (char_length(language) <= 10),
    created_at timestamptz not null default now(),
    primary key (user_id, week_start, scope)
);

alter table public.trade_reviews enable row level security;

drop policy if exists "own trade reviews" on public.trade_reviews;
create policy "own trade reviews" on public.trade_reviews
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

revoke all on public.trade_reviews from public, anon;
grant select, insert, update, delete on public.trade_reviews to authenticated;

-- "Delete all my Trade Log data" also removes the reviews.
create or replace function public.tradelog_delete_everything()
returns integer
language plpgsql
security definer
set search_path = public, vault
as $$
declare
    n integer := 0;
    r record;
begin
    for r in select id, secret_id from public.trade_connections where user_id = auth.uid() loop
        delete from public.trade_connections where id = r.id;
        delete from vault.secrets where id = r.secret_id;
        n := n + 1;
    end loop;
    delete from public.trade_reviews where user_id = auth.uid();
    return n;
end;
$$;

revoke all on function public.tradelog_delete_everything() from public, anon;
grant execute on function public.tradelog_delete_everything() to authenticated;

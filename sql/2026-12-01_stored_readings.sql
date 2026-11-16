-- 16 Nov 2026: the background worker saves each asset's readings next to its prices (stored_readings.py), so the
-- page no longer works them out on every visit after a price change (about half a second per asset).
-- Safe to run more than once. Run it in the Supabase SQL editor.

alter table public.asset_market add column if not exists readings jsonb;

-- The write guard, unchanged except that only the worker (the service role) can write readings.
create or replace function public.guard_asset_market_write()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    cutoff timestamptz := now() - interval '12 hours';
    ceiling_at constant timestamptz := now() + interval '5 minutes';
begin
    if auth.uid() is null then
        return new;
    end if;

    if new.sentiment_score is not null and (new.sentiment_score < 0 or new.sentiment_score > 100) then
        raise exception 'sentiment_score must be between 0 and 100';
    end if;
    if new.logo_url is not null and new.logo_url !~* '^https://' then
        raise exception 'logo_url must be an https address';
    end if;
    if new.market_cap is not null and new.market_cap < 0 then
        raise exception 'market_cap cannot be negative';
    end if;
    if new.market_rank is not null and (new.market_rank < 1 or new.market_rank > 1000000) then
        raise exception 'market_rank is out of range';
    end if;
    if pg_column_size(new.closes) > 262144
       or pg_column_size(new.prices) > 1048576
       or pg_column_size(new.sentiment_report) > 65536 then
        raise exception 'shared market data is too large';
    end if;
    if new.closes_updated_at > ceiling_at
       or new.sentiment_updated_at > ceiling_at
       or new.prices_updated_at > ceiling_at
       or new.market_stats_updated_at > ceiling_at
       or new.earnings_checked_at > ceiling_at then
        raise exception 'timestamps cannot be in the future';
    end if;

    -- Readings (stored_readings.py) come from the background worker only: a signed-in session cannot set them.
    if tg_op = 'INSERT' then
        new.readings := null;
        return new;
    end if;
    new.readings := old.readings;

    new.asset_key := old.asset_key;
    new.kind := old.kind;
    new.asset_id := old.asset_id;

    if old.closes is not null
       and (old.closes_updated_at is null or old.closes_updated_at > cutoff
            or new.closes_updated_at is null or new.closes_updated_at <= old.closes_updated_at) then
        new.closes := old.closes;
        new.closes_updated_at := old.closes_updated_at;
    end if;

    if old.prices is not null
       and (old.prices_updated_at is null or old.prices_updated_at > cutoff
            or new.prices_updated_at is null or new.prices_updated_at <= old.prices_updated_at) then
        new.prices := old.prices;
        new.prices_updated_at := old.prices_updated_at;
    end if;

    if old.sentiment_updated_at is not null
       and (old.sentiment_updated_at > cutoff
            or new.sentiment_updated_at is null or new.sentiment_updated_at <= old.sentiment_updated_at) then
        new.sentiment_score := old.sentiment_score;
        new.sentiment_report := old.sentiment_report;
        new.sentiment_updated_at := old.sentiment_updated_at;
    end if;

    if old.logo_url is not null then
        new.logo_url := old.logo_url;
    end if;

    -- Earnings dates: kept for 6 hours, then a newer check may replace them.
    if old.earnings_checked_at is not null
       and (old.earnings_checked_at > now() - interval '6 hours'
            or new.earnings_checked_at is null or new.earnings_checked_at <= old.earnings_checked_at) then
        new.next_earnings := old.next_earnings;
        new.earnings_checked_at := old.earnings_checked_at;
    end if;

    -- Market cap and rank follow the same rule: kept for 20 minutes, then a newer reading may replace them.
    if old.market_stats_updated_at is not null
       and (old.market_stats_updated_at > now() - interval '20 minutes'
            or new.market_stats_updated_at is null or new.market_stats_updated_at <= old.market_stats_updated_at) then
        new.market_cap := old.market_cap;
        new.market_rank := old.market_rank;
        new.market_stats_updated_at := old.market_stats_updated_at;
    end if;

    return new;
end;
$$;

drop trigger if exists guard_asset_market_write on public.asset_market;
create trigger guard_asset_market_write
    before insert or update on public.asset_market
    for each row
    execute function public.guard_asset_market_write();

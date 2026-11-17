-- 17 Nov 2026: the newest few daily bars of each asset, so the app can update the price history it already holds
-- instead of downloading every asset's whole history (about 500 bars) each time the worker refreshes prices (every
-- 5 to 10 minutes). The free plan allows 5 GB of data out a month; whole histories used most of it.
-- Safe to run more than once. Run it in the Supabase SQL editor.

create or replace function public.asset_recent_prices(wanted text[], bars integer default 3)
returns table (asset_key text, prices_updated_at timestamptz, recent jsonb)
language sql
stable
set search_path = public
as $$
    select market.asset_key,
           market.prices_updated_at,
           case when jsonb_typeof(market.prices) = 'array' and jsonb_array_length(market.prices) > 0
                then jsonb_path_query_array(market.prices,
                                            ('$[last - ' || greatest(least(coalesce(bars, 3), 30), 1) - 1 || ' to last]')::jsonpath)
                else '[]'::jsonb end
    from public.asset_market as market
    where market.asset_key = any (wanted);
$$;

revoke all on function public.asset_recent_prices(text[], integer) from public, anon;
grant execute on function public.asset_recent_prices(text[], integer) to authenticated, service_role;

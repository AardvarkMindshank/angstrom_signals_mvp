-- Trade Log: staking rewards and airdrops (26 Nov 2026). Safe to run more than once.
-- eToro pays crypto staking rewards as small new positions each month. They are kept apart from the trade numbers.
alter table public.trade_round_trips add column if not exists reward boolean not null default false;

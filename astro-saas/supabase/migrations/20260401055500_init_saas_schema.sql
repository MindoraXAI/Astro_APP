-- Initial SaaS schema for Astro Vedic platform
-- Safe to run on Supabase Postgres.

create extension if not exists "pgcrypto";

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  avatar_url text,
  plan text not null default 'free' check (plan in ('free', 'pro', 'lifetime')),
  charts_generated int not null default 0 check (charts_generated >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.charts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  full_name text not null,
  birth_date date not null,
  birth_time time not null,
  birth_location text not null,
  timezone text not null,
  latitude double precision not null,
  longitude double precision not null,
  ayanamsa text not null default 'lahiri',
  raw_calculation jsonb not null,
  ai_reading jsonb,
  created_at timestamptz not null default now(),
  is_public boolean not null default false
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  chart_id uuid not null references public.charts(id) on delete cascade,
  title text not null default 'Chart chat',
  messages jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  plan text not null check (plan in ('free', 'pro', 'lifetime')),
  status text not null default 'inactive',
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_charts_user_created on public.charts(user_id, created_at desc);
create index if not exists idx_chat_sessions_user_updated on public.chat_sessions(user_id, updated_at desc);
create index if not exists idx_usage_events_user_created on public.usage_events(user_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.charts enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.subscriptions enable row level security;
alter table public.usage_events enable row level security;

create policy "profiles_select_own"
on public.profiles for select
using (auth.uid() = id);

create policy "profiles_update_own"
on public.profiles for update
using (auth.uid() = id)
with check (auth.uid() = id);

create policy "profiles_insert_own"
on public.profiles for insert
with check (auth.uid() = id);

create policy "charts_select_own"
on public.charts for select
using (auth.uid() = user_id);

create policy "charts_insert_own"
on public.charts for insert
with check (auth.uid() = user_id);

create policy "charts_update_own"
on public.charts for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "chat_sessions_select_own"
on public.chat_sessions for select
using (auth.uid() = user_id);

create policy "chat_sessions_insert_own"
on public.chat_sessions for insert
with check (auth.uid() = user_id);

create policy "chat_sessions_update_own"
on public.chat_sessions for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "subscriptions_select_own"
on public.subscriptions for select
using (auth.uid() = user_id);

create policy "usage_events_select_own"
on public.usage_events for select
using (auth.uid() = user_id);

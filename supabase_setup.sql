-- Plant Label Generator: one-time Supabase setup
-- Paste this whole file into Supabase > SQL Editor > New query, then click Run.
-- It is safe to run again; it only creates things that don't exist yet.

-- 1. Invite list. Only emails in this table can save settings.
create table if not exists public.invited_users (
  email      text primary key check (email = lower(email)),
  note       text,
  invited_at timestamptz not null default now()
);

-- 2. Saved settings (template, font, sizes, printer nudge, chosen icon).
create table if not exists public.user_settings (
  email      text primary key references public.invited_users (email) on delete cascade,
  settings   jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- 3. How often each user loads each Plant Toolbox link.
create table if not exists public.plant_link_usage (
  email           text not null references public.invited_users (email) on delete cascade,
  url             text not null,
  common_name     text,
  scientific_name text,
  use_count       integer not null default 0,
  last_used       timestamptz not null default now(),
  primary key (email, url)
);

-- 4. One-row table the keep-alive job touches so the project never looks idle.
create table if not exists public.keepalive (
  id        integer primary key default 1 check (id = 1),
  pinged_at timestamptz not null default now()
);
insert into public.keepalive (id) values (1) on conflict (id) do nothing;

-- Lock every table down. With RLS on and no policies, only the secret key
-- (used by the Streamlit server) can read or write them.
alter table public.invited_users    enable row level security;
alter table public.user_settings    enable row level security;
alter table public.plant_link_usage enable row level security;
alter table public.keepalive        enable row level security;

-- Keep updated_at fresh on settings saves.
create or replace function public.touch_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists user_settings_touch on public.user_settings;
create trigger user_settings_touch
  before update on public.user_settings
  for each row execute function public.touch_updated_at();

-- Count plant link loads in one call (used by the app).
create or replace function public.record_plant_usage(p_email text, p_items jsonb)
returns void language sql set search_path = '' as $$
  insert into public.plant_link_usage as u
    (email, url, common_name, scientific_name, use_count, last_used)
  select distinct on (item->>'url')
         lower(p_email), item->>'url', item->>'common_name', item->>'scientific_name', 1, now()
  from jsonb_array_elements(p_items) as item
  where coalesce(item->>'url', '') <> ''
  on conflict (email, url) do update
    set use_count       = u.use_count + 1,
        common_name     = coalesce(excluded.common_name, u.common_name),
        scientific_name = coalesce(excluded.scientific_name, u.scientific_name),
        last_used       = now();
$$;
revoke execute on function public.record_plant_usage(text, jsonb) from public, anon, authenticated;

-- Keep-alive ping. This is the only thing the publishable key may call,
-- and all it does is update a timestamp.
create or replace function public.ping_keepalive()
returns timestamptz language sql security definer set search_path = '' as $$
  update public.keepalive set pinged_at = now() where id = 1 returning pinged_at;
$$;
revoke execute on function public.ping_keepalive() from public;
grant execute on function public.ping_keepalive() to anon;

-- 5. Private storage bucket for icons (2 per user, PNG, 2 MB max each).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('label-icons', 'label-icons', false, 2097152, array['image/png'])
on conflict (id) do nothing;

-- 6. Invite people. Replace the example with real Google account emails
--    (lowercase), and run just these lines again whenever you add someone.
-- insert into public.invited_users (email, note) values
--   ('you@example.com', 'owner'),
--   ('volunteer@example.com', 'EMG volunteer')
-- on conflict (email) do nothing;

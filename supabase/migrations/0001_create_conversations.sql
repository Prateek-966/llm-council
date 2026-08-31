-- Conversation storage for the Supabase backend (backend/storage_supabase.py).
-- Applied to the project already; kept here so the schema is reproducible.
create table public.conversations (
  id text primary key,
  created_at timestamptz not null default now(),
  title text not null default 'New Conversation',
  messages jsonb not null default '[]'::jsonb,
  message_count integer generated always as (jsonb_array_length(messages)) stored
);

create index conversations_created_at_idx on public.conversations (created_at desc);

-- RLS on with no policies: unreadable and unwritable with the anon/publishable key.
-- The backend uses the service-role key, which bypasses RLS.
alter table public.conversations enable row level security;

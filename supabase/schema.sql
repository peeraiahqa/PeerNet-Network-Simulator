-- PeerNet Network Simulator
-- Safe to run in the same Supabase project as PeerNet AI.
-- This script creates only simulator-specific objects.

create extension if not exists pgcrypto;

create table if not exists public.simulator_projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null default 'Untitled topology',
    description text not null default '',
    topology_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists simulator_projects_user_id_idx
on public.simulator_projects(user_id);

create index if not exists simulator_projects_updated_at_idx
on public.simulator_projects(updated_at desc);

alter table public.simulator_projects enable row level security;

drop policy if exists "simulator_projects_select_own"
on public.simulator_projects;

create policy "simulator_projects_select_own"
on public.simulator_projects
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "simulator_projects_insert_own"
on public.simulator_projects;

create policy "simulator_projects_insert_own"
on public.simulator_projects
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "simulator_projects_update_own"
on public.simulator_projects;

create policy "simulator_projects_update_own"
on public.simulator_projects
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "simulator_projects_delete_own"
on public.simulator_projects;

create policy "simulator_projects_delete_own"
on public.simulator_projects
for delete
to authenticated
using ((select auth.uid()) = user_id);

grant select, insert, update, delete
on public.simulator_projects
to authenticated;

-- Automatically maintain updated_at.
create or replace function public.set_simulator_project_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists simulator_projects_set_updated_at
on public.simulator_projects;

create trigger simulator_projects_set_updated_at
before update on public.simulator_projects
for each row
execute function public.set_simulator_project_updated_at();

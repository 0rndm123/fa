-- Apply manually in the existing portfolio_site Supabase SQL Editor.
-- Requires the existing private app_permissions table; never modifies SysTrd rows.
begin;
create or replace function app_private.fa_agent_current_permission()
returns table(role text, enabled boolean)
language sql stable security definer set search_path=''
as $$
  select p.role,p.enabled from app_private.app_permissions p
  where p.user_id=auth.uid() and p.app_id='fa_agent'
$$;
create or replace function public.fa_agent_current_permission()
returns table(role text,enabled boolean)
language sql stable security invoker set search_path=''
as $$ select * from app_private.fa_agent_current_permission() $$;
revoke all on function app_private.fa_agent_current_permission() from public,anon;
revoke all on function public.fa_agent_current_permission() from public,anon;
grant usage on schema app_private to authenticated;
grant execute on function app_private.fa_agent_current_permission() to authenticated;
grant execute on function public.fa_agent_current_permission() to authenticated;
-- Authorize an initial admin manually, replacing the email:
-- insert into app_private.app_permissions(user_id,app_id,role,enabled)
-- select id,'fa_agent','admin',true from auth.users where email='YOUR_EMAIL@example.com'
-- on conflict(user_id,app_id) do update set role='admin',enabled=true,updated_at=now();
commit;

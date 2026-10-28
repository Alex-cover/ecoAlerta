-- Proyecto EcoAlerta El Alto.
-- 09_datos_prueba.sql: deja la base VACÍA, solo con el usuario administrador.

-- 1. Crea (si no existe) la cuenta admin@ecoalerta.test como moderador.
-- Contraseña: Prueba123! -> CÁMBIELA después (Supabase -> Authentication -> Users).
-- 2. Borra lo que crean las pruebas automáticas (pytest): las cuentas @ecoalerta.test.
-- (menos el admin) con todos sus reportes, votos y fotos, y los reportes "[PRUEBA]".
-- Las cuentas reales (las que se registran en la app) NO se tocan.

-- Se puede ejecutar las veces que se quiera: después de correr las pruebas, se vuelve.
-- a ejecutar este archivo y la base queda limpia otra vez.

-- pgcrypto sirve para encriptar la contraseña.
create extension if not exists pgcrypto with schema extensions;


-- 1. Administrador.
-- El trigger trg_usuario_nuevo le crea el perfil.
-- Los campos *_token van en '' porque si son NULL el login falla.
insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
                        raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                        confirmation_token, recovery_token, email_change_token_new, email_change)
select '00000000-0000-0000-0000-000000000000', 'e0a1e000-0000-4000-8000-000000000001', 'authenticated',
       'authenticated', 'admin@ecoalerta.test', extensions.crypt('Prueba123!', extensions.gen_salt('bf')), now(),
       '{"provider": "email", "providers": ["email"]}'::jsonb,
       '{"nombre_usuario": "admin", "nombre_completo": "Administrador"}'::jsonb,
       now(), now(), '', '', '', ''
 where not exists (select 1 from auth.users where email = 'admin@ecoalerta.test');

-- Identidad "email": sin esto no puede iniciar sesión con correo y contraseña.
insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
select gen_random_uuid(), au.id, au.id::text,
       jsonb_build_object('sub', au.id::text, 'email', au.email, 'email_verified', true),
       'email', now(), now(), now()
  from auth.users au
 where au.email = 'admin@ecoalerta.test'
   and not exists (select 1 from auth.identities i where i.user_id = au.id and i.provider = 'email');

-- El admin es moderador.
update public.usuario set rol = 'moderador'
 where id_usuario = (select id from auth.users where email = 'admin@ecoalerta.test');


-- 2. Borrar lo de las pruebas.

-- Reportes de las cuentas de prueba (en cascada se borran sus votos, fotos, historial y características)
delete from public.reporte
 where id_usuario in (select id from auth.users
                       where email like '%@ecoalerta.test' and email <> 'admin@ecoalerta.test');

-- Reportes de prueba que haya hecho cualquier otra cuenta.
delete from public.reporte where descripcion like '[PRUEBA]%';

-- Votos que las cuentas de prueba dejaron en otros reportes.
delete from public.confirmacion
 where id_usuario in (select id from auth.users
                       where email like '%@ecoalerta.test' and email <> 'admin@ecoalerta.test');

-- Las cuentas de prueba (en cascada se borran su perfil en usuario y su identidad)
delete from auth.users where email like '%@ecoalerta.test' and email <> 'admin@ecoalerta.test';

-- Como borramos votos sin pasar por los triggers, volvemos a contar.
update public.reporte r
   set total_confirmaciones = (select count(*) from public.confirmacion c where c.id_reporte = r.id_reporte and c.sigue),
       total_ya_no_esta     = (select count(*) from public.confirmacion c where c.id_reporte = r.id_reporte and not c.sigue);

-- OJO: las fotos que subieron las pruebas quedan en Storage.
-- Para borrarlas: Supabase -> Storage -> evidencias -> seleccionar las carpetas -> Delete.


-- 3. Para revisar.
-- select email from auth.users; -- solo el admin (y las cuentas reales)
-- select nombre_usuario, rol from public.usuario;
-- select count(*) from public.reporte; -- 0 si nadie reportó todavía.

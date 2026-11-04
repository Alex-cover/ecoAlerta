-- Cambia el rol antiguo "estudiante" por "ciudadano" sin borrar cuentas.
-- Ejecutar una sola vez sobre una base existente.

begin;

alter table public.usuario
    drop constraint if exists ck_usuario_rol;

update public.usuario
   set rol = 'ciudadano'
 where rol = 'estudiante';

alter table public.usuario
    add constraint ck_usuario_rol
    check (rol in ('ciudadano', 'moderador'));

commit;

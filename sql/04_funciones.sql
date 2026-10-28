-- Proyecto EcoAlerta El Alto.
-- 04_funciones.sql: funciones que se llaman desde la app.

-- Borramos funciones de la versión anterior del proyecto (si existen)
drop function if exists public.es_admin() cascade;
drop function if exists public.usuario_activo() cascade;
drop function if exists public.confirmar_reporte(bigint, text) cascade;
drop function if exists public.reportes_cercanos(numeric, numeric, int, int, int) cascade;
drop function if exists public.asignar_rol(uuid, smallint) cascade;
drop function if exists public.cargar_zonas_geojson(jsonb) cascade;


-- ¿El usuario actual es moderador?
-- Es security definer para leer la tabla usuario sin pasar por RLS.
create or replace function public.es_moderador()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (select 1 from usuario where id_usuario = auth.uid() and rol = 'moderador');
$$;


-- Detalle de esta secci?n.
-- cambiar_estado: solo el moderador.
-- un reporte Solucionado ya no cambia.
-- a mano solo se pasa a Prioritario (3), En atención (4) o Solucionado (5)
-- solo se avanza, nunca se retrocede.
-- para Solucionado el comentario es obligatorio.
-- Detalle de esta secci?n.
create or replace function public.cambiar_estado(
    p_id_reporte bigint,
    p_id_estado  smallint,
    p_comentario text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_actual    estado%rowtype;
    v_destino   estado%rowtype;
    v_id_estado smallint;
begin
    if not es_moderador() then
        raise exception 'Solo un moderador puede cambiar el estado' using errcode = 'insufficient_privilege';
    end if;

    -- FOR UPDATE: si dos moderadores cambian el estado a la vez,
    -- el segundo espera y luego ve el estado ya cambiado.
    -- OJO: se bloquea solo la tabla reporte, sin JOIN. Con JOIN, el que espera.
    -- vuelve a juntar la fila nueva con el estado viejo y no encuentra nada.
    select id_estado into v_id_estado
      from reporte
     where id_reporte = p_id_reporte
       for update;
    if not found then
        raise exception 'El reporte no existe' using errcode = 'no_data_found';
    end if;
    select * into v_actual from estado where id_estado = v_id_estado;

    select * into v_destino from estado where id_estado = p_id_estado;

    if v_actual.es_final then
        raise exception 'El reporte ya está solucionado' using errcode = 'check_violation';
    end if;
    if p_id_estado not in (3, 4, 5) or v_destino.orden <= v_actual.orden then
        raise exception 'No se puede pasar de "%" a "%"', v_actual.nombre, v_destino.nombre
            using errcode = 'check_violation';
    end if;
    if p_id_estado = 5 and coalesce(btrim(p_comentario), '') = '' then
        raise exception 'Para marcar como Solucionado debe escribir un comentario' using errcode = 'check_violation';
    end if;

    -- Dejamos el usuario y el comentario para el trigger del historial.
    perform set_config('ecoalerta.id_usuario', auth.uid()::text, true);
    perform set_config('ecoalerta.comentario', coalesce(p_comentario, ''), true);
    update reporte set id_estado = p_id_estado where id_reporte = p_id_reporte;
end;
$$;

-- Detalle de esta secci?n.
-- votar: "Sigue ahí" (p_sigue = true) o "Ya no está" (p_sigue = false).
-- si el usuario no votó, guarda su voto.
-- si ya votó lo otro, cambia su voto (por ejemplo, ya limpiaron el lugar)
-- si vota lo mismo otra vez, da error.
-- Los triggers de confirmacion validan, cuentan y cambian el estado.
-- Devuelve el id del voto (para asociarle la foto de "ya no está").
-- Detalle de esta secci?n.
create or replace function public.votar(p_id_reporte bigint, p_sigue boolean)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id       bigint;    -- id del voto.
    v_sigue    boolean;   -- voto anterior del usuario (null si no votó)
    v_autor    uuid;
    v_estado   smallint;
    v_gravedad text;
    v_total    int;       -- votos "sigue ahí".
    v_total_no int;       -- votos "ya no está".
    v_nuevo    smallint;  -- estado nuevo (null si no cambia)
    v_comentario text;
begin
    -- 1. FOR UPDATE: los votos que llegan al mismo tiempo al mismo reporte se procesan uno por uno.
    -- Se bloquea solo la tabla reporte (sin JOIN, ver cambiar_estado()).
    select id_usuario, id_estado, gravedad into v_autor, v_estado, v_gravedad
      from reporte
     where id_reporte = p_id_reporte
       for update;
    if not found then
        raise exception 'El reporte no existe' using errcode = 'no_data_found';
    end if;

    -- 2. Reglas.
    if v_estado = 5 then
        raise exception 'El reporte ya está solucionado' using errcode = 'check_violation';
    end if;
    if v_autor = auth.uid() and p_sigue then
        raise exception 'No puede confirmar su propio reporte' using errcode = 'check_violation';
    end if;

    -- 3. Guardamos el voto nuevo o cambiamos el anterior.
    select id_confirmacion, sigue into v_id, v_sigue
      from confirmacion
     where id_reporte = p_id_reporte and id_usuario = auth.uid();

    if v_id is null then
        insert into confirmacion (id_reporte, id_usuario, sigue)
        values (p_id_reporte, auth.uid(), p_sigue)
        returning id_confirmacion into v_id;
    elsif v_sigue = p_sigue then
        raise exception 'Usted ya votó "%" en este reporte',
            case when p_sigue then 'Sigue ahí' else 'Ya no está' end using errcode = 'unique_violation';
    else
        update confirmacion set sigue = p_sigue, fecha = now() where id_confirmacion = v_id;
    end if;

    -- 4. Contadores: se suma al voto nuevo y, si cambió, se resta del anterior (en un solo UPDATE)
    update reporte
       set total_confirmaciones = total_confirmaciones
                                  + case when p_sigue then 1 else 0 end
                                  - case when v_sigue is true then 1 else 0 end,
           total_ya_no_esta     = total_ya_no_esta
                                  + case when p_sigue then 0 else 1 end
                                  - case when v_sigue is false then 1 else 0 end
     where id_reporte = p_id_reporte
    returning total_confirmaciones, total_ya_no_esta into v_total, v_total_no;

    -- 5. Cambio automático de estado.
    if v_total_no >= 3 then
        -- 3 vecinos dicen que ya no está: se da por solucionado.
        v_nuevo := 5;
        v_comentario := format('Automático: %s vecinos indicaron que ya no está', v_total_no);
    elsif v_gravedad = 'Alto' and v_total >= 5 and v_estado in (1, 2) then
        -- Gravedad Alto con 5 o más confirmaciones pasa a Prioritario.
        v_nuevo := 3;
    elsif v_total >= 3 and v_estado = 1 then
        -- Con 3 confirmaciones pasa a Confirmado.
        v_nuevo := 2;
    end if;

    if v_nuevo is not null then
        -- Usuario vacío = cambio automático (lo lee el trigger del historial)
        perform set_config('ecoalerta.id_usuario', '', true);
        perform set_config('ecoalerta.comentario',
                           coalesce(v_comentario, format('Automático: %s confirmaciones', v_total)), true);
        update reporte set id_estado = v_nuevo where id_reporte = p_id_reporte;
    end if;
    return v_id;
end;
$$;


-- Detalle de esta secci?n.
-- cambiar_rol: solo el moderador; pasa a un usuario a 'estudiante' o 'moderador'.
-- Nadie cambia su propio rol (así siempre queda al menos el que lo hace).
-- Detalle de esta secci?n.
create or replace function public.cambiar_rol(p_id_usuario uuid, p_rol text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not es_moderador() then
        raise exception 'Solo un moderador puede cambiar roles' using errcode = 'insufficient_privilege';
    end if;
    if p_id_usuario = auth.uid() then
        raise exception 'No puede cambiar su propio rol' using errcode = 'check_violation';
    end if;

    -- El CHECK ck_usuario_rol revisa que el rol sea válido.
    update usuario set rol = p_rol where id_usuario = p_id_usuario;
    if not found then
        raise exception 'El usuario no existe' using errcode = 'no_data_found';
    end if;
end;
$$;

-- El moderador puede eliminar vecinos. La cuenta de auth se borra y las
-- relaciones de sus reportes y votos se eliminan por las FK en cascada.
create or replace function public.eliminar_usuario(p_id_usuario uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_rol text;
begin
    if not es_moderador() then
        raise exception 'Solo un moderador puede eliminar usuarios' using errcode = 'insufficient_privilege';
    end if;
    if p_id_usuario = auth.uid() then
        raise exception 'No puede eliminar su propia cuenta' using errcode = 'check_violation';
    end if;

    select rol into v_rol
      from usuario
     where id_usuario = p_id_usuario
     for update;
    if not found then
        raise exception 'El usuario no existe' using errcode = 'no_data_found';
    end if;
    if v_rol <> 'estudiante' then
        raise exception 'Solo se pueden eliminar cuentas de vecinos' using errcode = 'check_violation';
    end if;

    -- Se borran primero sus datos para respetar bases instaladas con FK antiguas.
    delete from reporte where id_usuario = p_id_usuario;
    delete from confirmacion where id_usuario = p_id_usuario;

    -- El perfil se elimina mediante auth.users para no dejar una cuenta activa
    -- sin perfil en public.usuario.
    delete from auth.users where id = p_id_usuario;
end;
$$;


-- Detalle de esta secci?n.
-- editar_reporte (UPDATE del CRUD de reportes):
-- el autor, solo mientras el reporte está en "Reportado" (nadie lo votó todavía)
-- el moderador, siempre (por ejemplo, para quitar datos personales)
-- Solo cambia los datos que escribió el usuario. El código, la ubicación, el estado,
-- los votos y la fecha no se tocan. Las características se reemplazan por las nuevas.
-- Los CHECK de la tabla y el trigger de características siguen validando todo.
-- Detalle de esta secci?n.
create or replace function public.editar_reporte(
    p_id_reporte      bigint,
    p_id_tipo         smallint,
    p_gravedad        text,
    p_descripcion     text,
    p_tamano          text,
    p_frecuencia      text,
    p_horario         text,
    p_caracteristicas smallint[] default '{}'
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_autor  uuid;
    v_estado smallint;
begin
    -- FOR UPDATE: si a la vez alguien vota, uno espera al otro.
    select id_usuario, id_estado into v_autor, v_estado
      from reporte
     where id_reporte = p_id_reporte
       for update;
    if not found then
        raise exception 'El reporte no existe' using errcode = 'no_data_found';
    end if;

    if not es_moderador() then
        if v_autor is distinct from auth.uid() then
            raise exception 'Solo el autor o un moderador puede editar este reporte'
                using errcode = 'insufficient_privilege';
        end if;
        if v_estado <> 1 then
            raise exception 'Solo puede editar su reporte mientras está en "Reportado" (otros vecinos ya lo votaron)'
                using errcode = 'check_violation';
        end if;
    end if;

    update reporte
       set id_tipo = p_id_tipo, gravedad = p_gravedad, descripcion = p_descripcion,
           tamano = p_tamano, frecuencia = p_frecuencia, horario = p_horario
     where id_reporte = p_id_reporte;

    -- Las características se borran y se vuelven a marcar.
    delete from reporte_caracteristica where id_reporte = p_id_reporte;
    insert into reporte_caracteristica (id_reporte, id_caracteristica)
    select p_id_reporte, c from unnest(coalesce(p_caracteristicas, '{}')) as c;
end;
$$;


-- Solo usuarios con sesión pueden llamarlas.
revoke execute on function public.es_moderador(), public.cambiar_estado(bigint, smallint, text),
    public.votar(bigint, boolean), public.cambiar_rol(uuid, text),
    public.editar_reporte(bigint, smallint, text, text, text, text, text, smallint[]),
    public.eliminar_usuario(uuid) from public, anon;
grant execute on function public.es_moderador(), public.cambiar_estado(bigint, smallint, text),
    public.votar(bigint, boolean), public.cambiar_rol(uuid, text),
    public.editar_reporte(bigint, smallint, text, text, text, text, text, smallint[]),
    public.eliminar_usuario(uuid) to authenticated;

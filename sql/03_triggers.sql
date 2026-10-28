-- Proyecto EcoAlerta El Alto.
-- 03_triggers.sql: triggers con las reglas del negocio.

-- Id de estado: 1 Reportado, 2 Confirmado, 3 Prioritario, 4 En atención, 5 Solucionado.
-- "security definer" hace que la función corra con permisos del dueño (postgres),
-- así puede escribir en tablas que RLS no deja tocar al usuario (como seguimiento).

-- Borramos funciones de la versión anterior del proyecto (si existen)
drop function if exists public.fn_reporte_codigo() cascade;
drop function if exists public.fn_reporte_fecha_act() cascade;
drop function if exists public.fn_evidencia_limite() cascade;
-- Los votos ahora se cuentan dentro de votar() (04_funciones.sql)
drop function if exists public.fn_confirmacion_validar() cascade;
drop function if exists public.fn_confirmacion_aplicar() cascade;


-- Detalle de esta secci?n.
-- trg_reporte_preparar: ubicación, zona, código y estado inicial.
-- Detalle de esta secci?n.
create or replace function public.fn_reporte_preparar()
returns trigger
language plpgsql
set search_path = public, extensions
as $$
declare
    v_punto geometry;
begin
    -- Armamos el punto (PostGIS usa longitud, latitud)
    v_punto := ST_SetSRID(ST_MakePoint(new.longitud, new.latitud), 4326);
    new.ubicacion := v_punto::geography;

    -- Buscamos la zona que contiene el punto.
    select z.id_zona into new.id_zona
      from zona z
     where ST_Within(v_punto, z.geom)
     limit 1;

    -- Si no está en ninguna zona, no se guarda.
    if new.id_zona is null then
        raise exception 'La ubicación (%, %) no está dentro de ninguna zona de El Alto',
            new.latitud, new.longitud using errcode = 'check_violation';
    end if;

    -- Código REP-AAAA-000001 a partir del id (así nunca se repite)
    new.codigo := format('REP-%s-%s', to_char(new.fecha_creacion, 'YYYY'), lpad(new.id_reporte::text, 6, '0'));

    -- Todo reporte empieza en Reportado y sin votos.
    new.id_estado := 1;
    new.total_confirmaciones := 0;
    new.total_ya_no_esta := 0;
    return new;
end;
$$;

create or replace trigger trg_reporte_preparar
    before insert on public.reporte
    for each row execute function public.fn_reporte_preparar();


-- Detalle de esta secci?n.
-- trg_reporte_seguimiento: guarda en el historial la creación y cada cambio de estado.
-- cambiar_estado() deja el usuario y el comentario en variables de la transacción.
-- Detalle de esta secci?n.
create or replace function public.fn_reporte_seguimiento()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if tg_op = 'INSERT' then
        insert into seguimiento (id_reporte, id_estado_nuevo, id_usuario, comentario, fecha)
        values (new.id_reporte, new.id_estado, new.id_usuario, 'Reporte registrado', new.fecha_creacion);

    elsif new.id_estado <> old.id_estado then
        -- Si no hay usuario guardado, fue un cambio automático (usuario null)
        insert into seguimiento (id_reporte, id_estado_anterior, id_estado_nuevo, id_usuario, comentario)
        values (new.id_reporte, old.id_estado, new.id_estado,
                nullif(current_setting('ecoalerta.id_usuario', true), '')::uuid,
                nullif(current_setting('ecoalerta.comentario', true), ''));
    end if;
    return null;
end;
$$;

create or replace trigger trg_reporte_seguimiento
    after insert or update of id_estado on public.reporte
    for each row execute function public.fn_reporte_seguimiento();


-- Detalle de esta secci?n.
-- trg_reporte_caracteristica_validar: un detalle de un tipo (ej. "Llantas")
-- solo se puede marcar en reportes de ese tipo.
-- Detalle de esta secci?n.
create or replace function public.fn_reporte_caracteristica_validar()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    v_tipo_reporte smallint;
    v_tipo_carac   smallint;
    v_nombre       text;
begin
    select id_tipo into v_tipo_reporte from reporte where id_reporte = new.id_reporte;
    select id_tipo, nombre into v_tipo_carac, v_nombre
      from caracteristica where id_caracteristica = new.id_caracteristica;

    if v_tipo_carac is not null and v_tipo_carac <> v_tipo_reporte then
        raise exception 'La característica "%" no corresponde a este tipo de contaminación', v_nombre
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$;

create or replace trigger trg_reporte_caracteristica_validar
    before insert on public.reporte_caracteristica
    for each row execute function public.fn_reporte_caracteristica_validar();


-- Detalle de esta secci?n.
-- trg_usuario_nuevo: crea el perfil cuando alguien se registra.
-- Detalle de esta secci?n.
create or replace function public.fn_usuario_nuevo()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_nombre text;
begin
    -- La app manda el nombre de usuario en los metadatos; si no, usamos el correo.
    v_nombre := coalesce(nullif(new.raw_user_meta_data ->> 'nombre_usuario', ''), split_part(new.email, '@', 1));
    -- Si el nombre es muy corto o ya existe le agregamos un pedazo del id.
    if char_length(v_nombre) < 3 or exists (select 1 from public.usuario where nombre_usuario = v_nombre) then
        v_nombre := left(v_nombre, 21) || '_' || left(new.id::text, 8);
    end if;

    insert into public.usuario (id_usuario, nombre_usuario, nombre_completo)
    values (new.id, left(v_nombre, 30),
            coalesce(nullif(new.raw_user_meta_data ->> 'nombre_completo', ''), v_nombre));
    return new;
end;
$$;

create or replace trigger trg_usuario_nuevo
    after insert on auth.users
    for each row execute function public.fn_usuario_nuevo();

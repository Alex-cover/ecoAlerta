-- Proyecto EcoAlerta El Alto.
-- 02_tablas.sql: tablas, restricciones e índices (10 tablas)

-- Borrar lo anterior.
-- Así el script se puede ejecutar de nuevo desde cero.
-- OJO: borra todos los datos de la aplicación (no borra las cuentas de auth.users).
drop table if exists public.reporte_caracteristica, public.caracteristica,
    public.seguimiento, public.confirmacion, public.evidencia, public.reporte,
    public.usuario, public.zona, public.estado, public.tipo_contaminacion cascade;
-- Tablas de la versión anterior del proyecto.
drop table if exists public.rol, public.categoria_contaminacion, public.nivel_gravedad cascade;


-- Catálogos.

create table public.tipo_contaminacion (
    id_tipo smallint not null,
    nombre  text     not null,
    color   text     not null,   -- color del marcador en el mapa.
    icono   text     not null,   -- ícono de Material Icons para el mapa.
    constraint pk_tipo_contaminacion        primary key (id_tipo),
    constraint uq_tipo_contaminacion_nombre unique (nombre),
    constraint ck_tipo_contaminacion_color  check (color ~ '^#[0-9A-Fa-f]{6}$')
);

create table public.estado (
    id_estado smallint not null,
    nombre    text     not null,
    orden     smallint not null,
    es_final  boolean  not null default false,
    constraint pk_estado        primary key (id_estado),
    constraint uq_estado_nombre unique (nombre),
    constraint uq_estado_orden  unique (orden)
);

-- Zonas de El Alto con su polígono.
create table public.zona (
    id_zona  serial   not null,
    nombre   text     not null,
    distrito smallint not null,
    geom     geometry(MultiPolygon, 4326) not null,
    constraint pk_zona          primary key (id_zona),
    constraint uq_zona_nombre   unique (nombre),
    constraint ck_zona_distrito check (distrito between 1 and 14)
);


-- Usuarios.

-- Perfil del usuario. Lo crea un trigger cuando alguien se registra.
-- No guardamos CI, dirección ni teléfono.
create table public.usuario (
    id_usuario      uuid        not null,
    nombre_usuario  text        not null,
    nombre_completo text        not null,
    rol             text        not null default 'estudiante',
    fecha_registro  timestamptz not null default now(),
    constraint pk_usuario primary key (id_usuario),
    constraint fk_usuario_auth_users foreign key (id_usuario)
        references auth.users (id) on delete cascade,
    constraint uq_usuario_nombre_usuario unique (nombre_usuario),
    constraint ck_usuario_nombre_usuario check (char_length(nombre_usuario) between 3 and 30),
    constraint ck_usuario_rol check (rol in ('estudiante', 'moderador'))
);


-- Reportes.

create table public.reporte (
    id_reporte           bigint generated always as identity,
    codigo               text         not null,             -- lo genera el trigger.
    id_usuario           uuid         not null default auth.uid(),
    id_tipo              smallint     not null,
    gravedad             text         not null,
    id_estado            smallint     not null default 1,   -- 1 = Reportado.
    id_zona              int          not null,             -- lo asigna el trigger.
    descripcion          text         not null,
    tamano               text         not null,             -- tamaño del área afectada.
    frecuencia           text         not null,             -- cada cuánto pasa.
    horario              text,                              -- cuándo pasa (null = no sabe)
    latitud              numeric(9,6) not null,
    longitud             numeric(9,6) not null,
    ubicacion            geography(Point, 4326) not null,   -- lo calcula el trigger.
    total_confirmaciones int          not null default 0,   -- votos "sigue ahí" (trigger)
    total_ya_no_esta     int          not null default 0,   -- votos "ya no está" (trigger)
    fecha_creacion       timestamptz  not null default now(),
    constraint pk_reporte primary key (id_reporte),
    constraint fk_reporte_usuario foreign key (id_usuario)
        references public.usuario (id_usuario) on delete cascade,
    constraint fk_reporte_tipo    foreign key (id_tipo)    references public.tipo_contaminacion (id_tipo),
    constraint fk_reporte_estado  foreign key (id_estado)  references public.estado (id_estado),
    constraint fk_reporte_zona    foreign key (id_zona)    references public.zona (id_zona),
    constraint uq_reporte_codigo  unique (codigo),
    constraint ck_reporte_gravedad    check (gravedad in ('Bajo', 'Medio', 'Alto')),
    constraint ck_reporte_descripcion check (char_length(btrim(descripcion)) between 10 and 500),
    constraint ck_reporte_tamano      check (tamano in ('Pequeño', 'Mediano', 'Grande')),
    constraint ck_reporte_frecuencia  check (frecuencia in ('Primera vez', 'A veces', 'Todos los días', 'Permanente')),
    constraint ck_reporte_horario     check (horario in ('Mañana', 'Tarde', 'Noche')),
    constraint ck_reporte_total_confirmaciones check (total_confirmaciones >= 0),
    constraint ck_reporte_total_ya_no_esta     check (total_ya_no_esta >= 0)
);

-- Votos de los vecinos: sigue = true "Sigue ahí", false "Ya no está".
-- El voto se puede cambiar con la función votar().
create table public.confirmacion (
    id_confirmacion bigint generated always as identity,
    id_reporte      bigint      not null,
    id_usuario      uuid        not null default auth.uid(),
    sigue           boolean     not null default true,
    fecha           timestamptz not null default now(),
    constraint pk_confirmacion primary key (id_confirmacion),
    constraint fk_confirmacion_reporte foreign key (id_reporte)
        references public.reporte (id_reporte) on delete cascade,
    constraint fk_confirmacion_usuario foreign key (id_usuario)
        references public.usuario (id_usuario) on delete cascade,
    -- Un solo voto por usuario en cada reporte.
    constraint uq_confirmacion_reporte_usuario unique (id_reporte, id_usuario)
);

-- Fotos (el archivo está en Storage, aquí solo la ruta).
-- id_confirmacion se llena cuando la foto muestra que el problema ya no está.
create table public.evidencia (
    id_evidencia    bigint generated always as identity,
    id_reporte      bigint      not null,
    id_confirmacion bigint,                  -- null = foto del reporte.
    ruta_archivo    text        not null,
    latitud_captura numeric(9,6),
    longitud_captura numeric(9,6),
    precision_captura numeric(8,2),
    distancia_metros numeric(10,2),
    verificacion_ubicacion text not null default 'Sin verificación',
    fecha_subida    timestamptz not null default now(),
    constraint pk_evidencia primary key (id_evidencia),
    constraint fk_evidencia_reporte foreign key (id_reporte)
        references public.reporte (id_reporte) on delete cascade,
    constraint fk_evidencia_confirmacion foreign key (id_confirmacion)
        references public.confirmacion (id_confirmacion) on delete cascade,
    constraint uq_evidencia_ruta_archivo unique (ruta_archivo),
    constraint ck_evidencia_verificacion check
        (verificacion_ubicacion in ('Ubicación verificada', 'Inconsistencia de ubicación', 'Sin verificación'))
);

-- Historial de estados. Solo lo llenan los triggers.
create table public.seguimiento (
    id_seguimiento     bigint generated always as identity,
    id_reporte         bigint      not null,
    id_estado_anterior smallint,              -- null al crear el reporte.
    id_estado_nuevo    smallint    not null,
    id_usuario         uuid,                  -- null = cambio automático del sistema.
    comentario         text,
    fecha              timestamptz not null default now(),
    constraint pk_seguimiento primary key (id_seguimiento),
    constraint fk_seguimiento_reporte foreign key (id_reporte)
        references public.reporte (id_reporte) on delete cascade,
    constraint fk_seguimiento_estado_anterior foreign key (id_estado_anterior)
        references public.estado (id_estado),
    constraint fk_seguimiento_estado_nuevo foreign key (id_estado_nuevo)
        references public.estado (id_estado),
    constraint fk_seguimiento_usuario foreign key (id_usuario)
        references public.usuario (id_usuario) on delete set null
);


-- Características.

-- Catálogo de características que el usuario marca al reportar.
-- id_tipo null = sirve para cualquier tipo ("Cerca de" y "Efectos");
-- si tiene id_tipo, es un detalle de ese tipo (ej. "Llantas" en Quema de basura).
create table public.caracteristica (
    id_caracteristica smallint not null,
    id_tipo           smallint,
    grupo             text     not null,
    nombre            text     not null,
    constraint pk_caracteristica primary key (id_caracteristica),
    constraint fk_caracteristica_tipo foreign key (id_tipo)
        references public.tipo_contaminacion (id_tipo),
    constraint ck_caracteristica_grupo check (grupo in ('Cerca de', 'Efectos', 'Detalle')),
    -- "nulls not distinct": tampoco se repite el nombre entre las generales (id_tipo null)
    constraint uq_caracteristica_tipo_nombre unique nulls not distinct (id_tipo, nombre)
);

-- Características marcadas en cada reporte (relación muchos a muchos)
create table public.reporte_caracteristica (
    id_reporte        bigint   not null,
    id_caracteristica smallint not null,
    constraint pk_reporte_caracteristica primary key (id_reporte, id_caracteristica),
    constraint fk_reporte_caracteristica_reporte foreign key (id_reporte)
        references public.reporte (id_reporte) on delete cascade,
    constraint fk_reporte_caracteristica_caracteristica foreign key (id_caracteristica)
        references public.caracteristica (id_caracteristica)
);


-- Índices.

-- Espaciales (GIST) para ST_Within y DBSCAN.
create index idx_zona_geom         on public.zona    using gist (geom);
create index idx_reporte_ubicacion on public.reporte using gist (ubicacion);

-- Para los filtros del mapa.
create index idx_reporte_fecha_creacion on public.reporte (fecha_creacion);
create index idx_reporte_estado         on public.reporte (id_estado);
create index idx_reporte_tipo           on public.reporte (id_tipo);
create index idx_reporte_zona           on public.reporte (id_zona);
create index idx_seguimiento_reporte    on public.seguimiento (id_reporte, fecha);

-- Para contar reportes por característica (v_resumen_caracteristica)
create index idx_reporte_caracteristica_caracteristica on public.reporte_caracteristica (id_caracteristica);

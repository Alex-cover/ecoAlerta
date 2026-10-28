-- Proyecto EcoAlerta El Alto.
-- 06_vistas.sql: vistas para la app y consultas de análisis.
-- security_invoker = true: la vista respeta las políticas RLS de quien consulta.

-- Vistas de una versión anterior (esos datos ahora los calcula la app)
drop view if exists public.v_resumen_caracteristica, public.v_reportes_por_semana;


-- Reporte con los nombres de tipo, estado, zona y autor (la usa el mapa y el detalle)
create or replace view public.v_reporte_detalle with (security_invoker = true) as
select r.id_reporte, r.codigo, r.descripcion, r.gravedad, r.latitud, r.longitud,
       r.total_confirmaciones, r.fecha_creacion,
       r.id_usuario, u.nombre_usuario,
       r.id_tipo,    t.nombre as tipo, t.color,
       r.id_estado,  e.nombre as estado, e.orden as orden_estado, e.es_final,
       r.id_zona,    z.nombre as zona,
       r.total_ya_no_esta, t.icono,
       r.tamano, r.frecuencia, r.horario
  from public.reporte r
  join public.usuario u            on u.id_usuario = r.id_usuario
  join public.tipo_contaminacion t on t.id_tipo    = r.id_tipo
  join public.estado e             on e.id_estado  = r.id_estado
  join public.zona z               on z.id_zona    = r.id_zona;


-- Zonas con más reportes, separados por estado.
create or replace view public.v_resumen_zona with (security_invoker = true) as
select z.nombre as zona,
       count(r.id_reporte)                     as total,
       count(*) filter (where r.id_estado = 1) as reportados,
       count(*) filter (where r.id_estado = 2) as confirmados,
       count(*) filter (where r.id_estado = 3) as prioritarios,
       count(*) filter (where r.id_estado = 4) as en_atencion,
       count(*) filter (where r.id_estado = 5) as solucionados
  from public.zona z
  left join public.reporte r on r.id_zona = z.id_zona
 group by z.id_zona, z.nombre;


-- Problemas más frecuentes: reportes por tipo.
create or replace view public.v_resumen_tipo with (security_invoker = true) as
select t.nombre as tipo,
       count(r.id_reporte)                          as total,
       count(*) filter (where r.gravedad = 'Alto')  as gravedad_alta,
       count(*) filter (where r.id_estado = 5)      as solucionados
  from public.tipo_contaminacion t
  left join public.reporte r on r.id_tipo = t.id_tipo
 group by t.id_tipo, t.nombre;


-- Focos recurrentes con DBSCAN: grupos de 3 o más reportes del mismo tipo a menos de 100 m.
-- Pasamos los puntos a UTM 19S (EPSG:32719) para que la distancia esté en metros.
create or replace view public.v_focos_recurrentes with (security_invoker = true) as
with puntos as (
    select r.id_reporte, r.codigo, r.id_tipo, r.id_zona,
           ST_Transform(r.ubicacion::geometry, 32719) as geom,
           ST_ClusterDBSCAN(ST_Transform(r.ubicacion::geometry, 32719), eps => 100, minpoints => 3)
               over (partition by r.id_tipo) as grupo
      from public.reporte r
)
select t.nombre as tipo,
       min(z.nombre) as zona,
       count(*) as total_reportes,
       string_agg(p.codigo, ', ' order by p.codigo) as codigos,
       -- Centro del foco, de vuelta en latitud/longitud.
       round(ST_Y(ST_Transform(ST_Centroid(ST_Collect(p.geom)), 4326))::numeric, 6) as latitud,
       round(ST_X(ST_Transform(ST_Centroid(ST_Collect(p.geom)), 4326))::numeric, 6) as longitud
  from puntos p
  join public.tipo_contaminacion t on t.id_tipo = p.id_tipo
  join public.zona z               on z.id_zona = p.id_zona
 where p.grupo is not null           -- los que no forman grupo quedan en null.
 group by t.nombre, p.id_tipo, p.grupo;

-- Proyecto EcoAlerta El Alto.
-- 07_realtime.sql: tablas que envían cambios en tiempo real.

-- Supabase Realtime manda a la app los cambios de las tablas que están en la.
-- publicación "supabase_realtime" (respetando RLS).

do $$
declare
    v_tabla text;
begin
    -- En Supabase la publicación ya existe; la creamos solo por si falta.
    if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        create publication supabase_realtime;
    end if;

    -- Agregamos las tablas si todavía no están (evidencia: para ver las fotos nuevas)
    foreach v_tabla in array array['reporte', 'confirmacion', 'seguimiento', 'evidencia']
    loop
        if not exists (
            select 1 from pg_publication_tables
             where pubname = 'supabase_realtime'
               and schemaname = 'public'
               and tablename = v_tabla
        ) then
            execute format('alter publication supabase_realtime add table public.%I', v_tabla);
        end if;
    end loop;
end;
$$;

-- Con "full" los cambios traen también los valores anteriores,
-- así la app sabe por ejemplo que el estado pasó de Reportado a Confirmado.
alter table public.reporte replica identity full;

-- Para revisar:
-- select schemaname, tablename from pg_publication_tables where pubname = 'supabase_realtime';

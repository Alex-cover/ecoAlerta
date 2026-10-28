-- Proyecto EcoAlerta El Alto.
-- 05_rls.sql: seguridad a nivel de fila (RLS) y Storage.

-- Con RLS activo, si no hay una política que lo permita, no se puede hacer nada.
-- No hay políticas de UPDATE: los reportes se editan solo con editar_reporte().
-- La única política de DELETE es la de reporte (autor en "Reportado" o moderador).
-- El estado solo cambia con cambiar_estado(), los votos con votar() y el rol con.
-- cambiar_rol() (security definer).

-- Borramos las políticas anteriores de las tablas, así este archivo se puede volver a ejecutar solo.
do $$
declare
    p record;
begin
    for p in select policyname, tablename from pg_policies where schemaname = 'public' loop
        execute format('drop policy %I on public.%I', p.policyname, p.tablename);
    end loop;
end;
$$;

alter table public.tipo_contaminacion enable row level security;
alter table public.estado             enable row level security;
alter table public.zona               enable row level security;
alter table public.usuario            enable row level security;
alter table public.reporte            enable row level security;
alter table public.evidencia          enable row level security;
alter table public.confirmacion       enable row level security;
alter table public.seguimiento        enable row level security;
alter table public.caracteristica     enable row level security;
alter table public.reporte_caracteristica enable row level security;

-- Leer: cualquier usuario con sesión (en las 10 tablas)
create policy leer on public.tipo_contaminacion for select to authenticated using (true);
create policy leer on public.estado             for select to authenticated using (true);
create policy leer on public.zona               for select to authenticated using (true);
create policy leer on public.usuario            for select to authenticated using (true);
create policy leer on public.reporte            for select to authenticated using (true);
create policy leer on public.evidencia          for select to authenticated using (true);
create policy leer on public.confirmacion       for select to authenticated using (true);
create policy leer on public.seguimiento        for select to authenticated using (true);
create policy leer on public.caracteristica     for select to authenticated using (true);
create policy leer on public.reporte_caracteristica for select to authenticated using (true);

-- Crear reportes solo a nombre propio.
create policy crear_propio on public.reporte
    for insert to authenticated with check (id_usuario = auth.uid());

-- Eliminar reportes (DELETE del CRUD): el autor mientras está en "Reportado", o un moderador.
-- En cascada se borran sus votos, fotos, historial y características.
create policy eliminar_autor_o_moderador on public.reporte
    for delete to authenticated
    using ((id_usuario = auth.uid() and id_estado = 1) or public.es_moderador());

-- confirmacion no tiene política de INSERT: los votos solo se guardan con votar()

-- Solo el autor marca las características de su reporte.
-- (caracteristica no tiene política de INSERT: el catálogo se carga por SQL)
create policy crear_autor on public.reporte_caracteristica
    for insert to authenticated
    with check (exists (select 1 from public.reporte r
                         where r.id_reporte = reporte_caracteristica.id_reporte and r.id_usuario = auth.uid()));

-- Fotos: el autor sube las del reporte, y quien votó "ya no está" sube la de su voto.
create policy crear_propia on public.evidencia
    for insert to authenticated
    with check (
        (id_confirmacion is null
         and exists (select 1 from public.reporte r
                      where r.id_reporte = evidencia.id_reporte and r.id_usuario = auth.uid()))
        or exists (select 1 from public.confirmacion c
                    where c.id_confirmacion = evidencia.id_confirmacion
                      and c.id_reporte = evidencia.id_reporte
                      and c.id_usuario = auth.uid() and not c.sigue));


-- Storage (bucket "evidencias")
-- Bucket privado: las fotos se ven con URL firmadas.
-- Ruta de cada foto: <id del usuario>/<id_reporte>/<nombre>.jpg.
insert into storage.buckets (id, name, public)
values ('evidencias', 'evidencias', false)
on conflict (id) do nothing;

-- Borramos las políticas de Storage de la versión anterior (si existen)
drop policy if exists evidencias_select on storage.objects;
drop policy if exists evidencias_insert on storage.objects;
drop policy if exists evidencias_delete_admin on storage.objects;
drop policy if exists evidencias_delete on storage.objects;

create policy evidencias_select on storage.objects
    for select to authenticated using (bucket_id = 'evidencias');

-- Cada usuario sube solo dentro de su carpeta.
create policy evidencias_insert on storage.objects
    for insert to authenticated
    with check (bucket_id = 'evidencias' and (storage.foldername(name))[1] = auth.uid()::text);

-- Al eliminar un reporte, la app borra después sus archivos.
-- Solo se puede borrar un archivo que ya no pertenece a ningún reporte (sin fila en evidencia).
create policy evidencias_delete on storage.objects
    for delete to authenticated
    using (bucket_id = 'evidencias'
           and not exists (select 1 from public.evidencia e where e.ruta_archivo = storage.objects.name));

-- Proyecto EcoAlerta El Alto.
-- 01_extensiones.sql: extensiones que usa el proyecto.

-- PostGIS para guardar puntos y polígonos y hacer consultas espaciales.
-- Supabase recomienda instalarla en el esquema "extensions".
create extension if not exists postgis with schema extensions;

-- Para revisar que se instaló:
-- select extensions.postgis_full_version();

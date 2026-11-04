# Voz Ambiental

Sistema para reportar y dar seguimiento a focos de contaminación en El Alto, con mapa
(OpenStreetMap), confirmaciones de los vecinos y actualización en tiempo real.
Proyecto final de Base de Datos II (Supabase + PostGIS + Python/NiceGUI).

Las evidencias pueden tomarse directamente desde el celular. La aplicación solicita la
ubicación del navegador al capturar o subir la foto y la compara con el punto del mapa
(rango de 100 metros). El reporte no se bloquea: la evidencia queda como **Ubicación
verificada**, **Inconsistencia de ubicación** o **Sin verificación** para revisión del moderador.

## Si te pasaron el proyecto en un zip

La base de datos ya está lista en Supabase y `config.py` ya trae las claves. Solo hay que:

1. Instalar **Python 3.11 o superior** (en Windows marcar "Add Python to PATH").
2. Abrir una terminal **dentro de esta carpeta** y ejecutar:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```
   (En Mac/Linux el segundo comando es `source venv/bin/activate`.)
3. Abrir http://localhost:8080 y registrarse.

⚠️ **No ejecutar los archivos de `sql/`**: `02_tablas.sql` borra todos los datos de la app.

Si la base ya existía antes del cambio de `estudiante` a `ciudadano`, ejecutar una vez
`sql/10_migrar_roles_ciudadanos.sql` en el SQL Editor de Supabase. Esta consulta conserva
las cuentas y solo cambia el nombre del rol.

## Instalación (desde cero, con una base de Supabase nueva)

1. **Base de datos**: en el SQL Editor de Supabase ejecutar en orden los archivos de `sql/`
   (`01_extensiones.sql` … `09_datos_prueba.sql`).
2. **Python 3.11 o superior**:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Claves**: copiar `config_ejemplo.py` como `config.py` y poner la URL y la clave `anon`
   (Supabase → Project Settings → API).
4. **Registro sin verificar el correo**: Supabase → Authentication → Sign In / Providers → Email →
   desactivar **Confirm email** y guardar.

## Ejecutar

```
python main.py
```

Abrir http://localhost:8080

La base empieza **vacía**, solo con el administrador:
- `admin@ecoalerta.test`, contraseña `Prueba123!` (moderador). **Cambiar la contraseña** en
  Supabase → Authentication → Users.

Los vecinos se registran desde la app. Para volver moderador a alguien: entrar como admin →
**Usuarios** → "Hacer moderador".

## Pruebas

```
pytest pruebas -v
```

Las pruebas crean sus propias cuentas (`vecino1@ecoalerta.test`, …) y reportes `[PRUEBA]`.
Después de guardar las evidencias, volver a ejecutar `sql/09_datos_prueba.sql` para dejar la base limpia
(y borrar en Storage → `evidencias` las fotos de prueba).

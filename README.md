# EcoAlerta El Alto

Sistema para reportar y dar seguimiento a focos de contaminación en El Alto, con mapa
(OpenStreetMap), confirmaciones de los vecinos y actualización en tiempo real.
Proyecto final de Base de Datos II (Supabase + PostGIS + Python/NiceGUI).

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

## Publicar en internet con Render

La aplicación puede publicarse en un servicio web como Render. Supabase sigue siendo el
servicio de base de datos, autenticación, archivos y tiempo real.

1. Sube el proyecto a un repositorio privado de GitHub. No subas `config.py`, la clave
   `service_role`, contraseñas ni archivos `.env`.
2. En Render crea un **New → Web Service** y conecta el repositorio.
3. Usa esta configuración:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python main.py`
4. En **Environment Variables** agrega:
   - `SUPABASE_URL`: la URL de Supabase.
   - `SUPABASE_KEY`: la clave pública `anon` de Supabase, nunca `service_role`.
   - `CLAVE_SESION`: una cadena larga y aleatoria, diferente de la usada localmente.
5. En Supabase, en **Authentication → URL Configuration**, coloca la URL pública de
   Render como **Site URL**. Si usas confirmación de correo, agrega también esa URL en
   **Redirect URLs**.
6. Espera el despliegue y abre la URL que entrega Render. Tus compañeros podrán registrarse
   y subir reportes desde esa dirección.

El programa escucha en `0.0.0.0` y usa automáticamente el puerto `PORT` que entrega el
hosting. No ejecutes `sql/02_tablas.sql` sobre una base que ya contiene datos, porque
ese archivo recrea las tablas.

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

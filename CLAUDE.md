# EcoAlerta El Alto — Especificación del proyecto

Proyecto final de **Base de Datos II** (I.T.D.B. – Sistemas Informáticos).
Sistema georreferenciado en tiempo real para registrar, confirmar y dar seguimiento a focos de
contaminación ambiental reportados por estudiantes que viven en **El Alto (Bolivia)**.

> El componente central es la **base de datos**: modelado, integridad, consultas, concurrencia y
> comunicación de cambios en tiempo real. La interfaz es secundaria.
>
> Versión **simplificada**: se implementa lo que pide el enunciado oficial, sin extras.

## Stack obligatorio

| Capa          | Tecnología                                     |
| ------------- | ---------------------------------------------- |
| Base de datos | Supabase (PostgreSQL + **PostGIS**)            |
| Tiempo real   | Supabase Realtime (`postgres_changes`)         |
| Autenticación | Supabase Auth (email + contraseña)             |
| Archivos      | Supabase Storage (bucket `evidencias`)         |
| Aplicación    | Python 3.11+ con **NiceGUI**                   |
| Mapa          | OpenStreetMap mediante `ui.leaflet` de NiceGUI |
| Fotos         | Pillow y opencv-python                         |
| Pruebas       | pytest                                         |

Todo debe funcionar con el **plan gratuito** de Supabase. Sin servicios de pago.

---

## 1. Problema a resolver

En distintas zonas de El Alto se presentan problemas ambientales: acumulación de residuos sólidos,
microbasurales, quema de basura y aguas residuales. Esa información está **dispersa**, **no está
georreferenciada**, **no tiene historial** y no permite saber si el problema sigue, si otros vecinos
lo confirmaron o si recibió atención.

## 2. Justificación social

El sistema transforma observaciones aisladas en información **organizada, georreferenciada, histórica
y actualizada**. Un reporte puede ser confirmado, clasificado, priorizado, seguido y marcado como
solucionado. El tiempo real hace que todos los usuarios conectados vean al instante los nuevos
reportes, confirmaciones y cambios de estado.

## 3. Objetivos

### 3.1 Objetivo general

Desarrollar un sistema georreferenciado en tiempo real para registrar, monitorear y dar seguimiento a
focos de contaminación ambiental en El Alto, utilizando Supabase, Python y OpenStreetMap, aplicando
los conocimientos de Base de Datos II.

### 3.2 Objetivos específicos

1. Implementar la base de datos en Supabase/PostgreSQL con claves, restricciones y reglas de integridad.
2. Implementar actualización en tiempo real para nuevos reportes, confirmaciones y cambios de estado.
3. Desarrollar en Python una aplicación que permita registrar, consultar, filtrar y actualizar información.
4. Representar los focos de contaminación sobre un mapa basado en OpenStreetMap.
5. Generar consultas que identifiquen problemas frecuentes, focos recurrentes y zonas con más reportes.

---

## 4. Datos de un reporte

CRUD de reportes en `consultas.py`: `crear_reporte` (C), `ver_reporte` / `listar_reportes` (R),
`editar_reporte` (U), `eliminar_reporte` (D).

| Dato                    | Campo en BD            | Condición   | Regla                                                       |
| ----------------------- | ---------------------- | ----------- | ----------------------------------------------------------- |
| Código/ID               | `id_reporte`, `codigo` | Obligatorio | `codigo` único `REP-AAAA-000001`, generado por trigger      |
| Usuario                 | `id_usuario`           | Obligatorio | FK a `usuario`; se toma de `auth.uid()`                     |
| Tipo de contaminación   | `id_tipo`              | Obligatorio | FK a `tipo_contaminacion` (3 tipos)                         |
| Descripción             | `descripcion`          | Obligatorio | Entre 10 y 500 caracteres; sin datos personales de terceros |
| Nivel de gravedad       | `gravedad`             | Obligatorio | `CHECK` en 'Bajo', 'Medio', 'Alto'                          |
| Latitud / longitud      | `latitud`, `longitud`  | Obligatorio | Debe caer dentro de una zona de El Alto                     |
| Ubicación espacial      | `ubicacion`            | Automático  | geography(Point), calculada por trigger                     |
| Fecha y hora            | `fecha_creacion`       | Automático  | `DEFAULT now()`                                             |
| Estado                  | `id_estado`            | Obligatorio | Siempre empieza en "Reportado" (lo fuerza el trigger)       |
| Evidencia               | tabla `evidencia`      | Recomendado | Fotos con rostros y placas difuminados                      |
| Tamaño del área         | `tamano`               | Obligatorio | `CHECK` en 'Pequeño', 'Mediano', 'Grande'                   |
| Frecuencia              | `frecuencia`           | Obligatorio | `CHECK` en 'Primera vez', 'A veces', 'Todos los días', 'Permanente' |
| Horario                 | `horario`              | Opcional    | `CHECK` en 'Mañana', 'Tarde', 'Noche'                       |
| Características         | `reporte_caracteristica` | Opcional  | Casillas: detalles del tipo, "Cerca de" y "Efectos"        |
| Zona/sector             | `id_zona`              | Obligatorio | Asignada por trigger con `ST_Within`                        |
| Total de confirmaciones | `total_confirmaciones` | Automático  | Votos "Sigue ahí", mantenido por trigger                    |
| Total "ya no está"      | `total_ya_no_esta`     | Automático  | Votos "Ya no está", mantenido por trigger                   |

### Tipos de contaminación (7)

| id | Tipo             | Color     | Ícono (Material Icons)  |
| -- | ---------------- | --------- | ----------------------- |
| 1  | Residuos sólidos | `#1baf7a` | `delete`                |
| 2  | Quema de basura  | `#eb6834` | `local_fire_department` |
| 3  | Aguas residuales | `#2a78d6` | `water_drop`            |
| 4  | Emisiones        | `#5f6b7a` | `factory`               |
| 5  | Escombros        | `#9c6b3e` | `construction`          |
| 6  | Malos olores     | `#8e44ad` | `air`                   |
| 7  | Otro             | `#d4a017` | `help`                  |

Con "Otro" el usuario explica en la descripción de qué se trata. Los usuarios no crean tipos nuevos.

### Gravedad

| Nivel     | Criterio                                                                                    |
| --------- | ------------------------------------------------------------------------------------------- |
| **Bajo**  | Área pequeña, sin riesgo inmediato para la salud.                                           |
| **Medio** | Área mediana o molestia continua; afecta el paso o la convivencia.                          |
| **Alto**  | Riesgo para la salud o el agua; cerca de escuelas, mercados, centros de salud o ríos.       |

### Estados y transiciones

| Estado      | Cómo se llega                                                     | Quién               |
| ----------- | ----------------------------------------------------------------- | ------------------- |
| Reportado   | Al crear el reporte                                               | Sistema             |
| Confirmado  | Al llegar a **3 confirmaciones** de usuarios distintos            | Trigger             |
| Prioritario | Gravedad Alto y **5 o más confirmaciones**, o decisión del moderador | Trigger / moderador |
| En atención | Una autoridad o junta vecinal está actuando                       | Moderador           |
| Solucionado | El moderador lo marca (requiere comentario), o **3 vecinos votan "Ya no está"** | Moderador / Trigger |

Un reporte **Solucionado** no puede recibir votos ni cambiar de estado.

### Votos de los vecinos

- Cada vecino tiene **un voto por reporte**: "Sigue ahí" (confirma) o "Ya no está".
- Puede **cambiar su voto** (por ejemplo, confirmó y después ve que limpiaron el lugar); los contadores se ajustan.
- El autor **no** puede votar "Sigue ahí" en su propio reporte, pero **sí** "Ya no está".
- Con "Ya no está" se puede subir una **foto** de cómo está el lugar ahora.
- Bajar el número de confirmaciones al cambiar un voto no hace retroceder el estado.

---

## 5. Diseño de la base de datos (10 tablas)

Esquema `public`. Nombres en español, `snake_case`, singular. Todas las restricciones con nombre.

- **tipo_contaminacion**: `id_tipo` PK, `nombre` UNIQUE, `color` CHECK hexadecimal, `icono`.
- **estado**: `id_estado` PK, `nombre` UNIQUE, `orden` UNIQUE, `es_final`.
- **zona** (distritos de El Alto): `id_zona` PK, `nombre` UNIQUE, `distrito` CHECK 1–14, `geom` geometry(MultiPolygon, 4326)
  con índice GIST. Límites aproximados sacados de OpenStreetMap (ver `08_datos_catalogo.sql`); en la app se llama "Distrito".
- **usuario**: `id_usuario` PK/FK → `auth.users` ON DELETE CASCADE, `nombre_usuario` UNIQUE CHECK 3–30,
  `nombre_completo`, `rol` CHECK en ('estudiante', 'moderador') DEFAULT 'estudiante', `fecha_registro`.
  Se crea con un trigger al registrarse. El rol moderador se asigna desde el Table Editor de Supabase.
- **reporte**: columnas de la sección 4. Índices GIST en `ubicacion` y B-tree en `fecha_creacion`,
  `id_estado`, `id_tipo`, `id_zona`.
- **evidencia**: `id_evidencia` PK, `id_reporte` FK ON DELETE CASCADE, `id_confirmacion` FK (NULL = foto
  del reporte; si no, foto de un voto "Ya no está"), `ruta_archivo` UNIQUE, `fecha_subida`.
- **confirmacion** (votos): `id_confirmacion` PK, `id_reporte` FK, `id_usuario` FK, `sigue` boolean, `fecha`,
  **UNIQUE (`id_reporte`, `id_usuario`)**.
- **seguimiento**: `id_seguimiento` PK, `id_reporte` FK, `id_estado_anterior`, `id_estado_nuevo`,
  `id_usuario` (NULL = cambio automático), `comentario`, `fecha`.
- **caracteristica** (catálogo, se carga solo por SQL): `id_caracteristica` PK, `id_tipo` FK (NULL = general),
  `grupo` CHECK en ('Cerca de', 'Efectos', 'Detalle'), `nombre`, UNIQUE NULLS NOT DISTINCT (`id_tipo`, `nombre`).
- **reporte_caracteristica** (muchos a muchos): PK (`id_reporte`, `id_caracteristica`); solo el autor la llena.

### Triggers

| Trigger                    | Momento                                   | Qué hace                                                                 |
| -------------------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| `trg_reporte_preparar`     | `reporte` BEFORE INSERT                   | Calcula `ubicacion`, asigna zona (`ST_Within`), genera `codigo`, estado inicial |
| `trg_reporte_seguimiento`  | `reporte` AFTER INSERT / UPDATE OF estado | Inserta una fila en `seguimiento`                                        |
| `trg_usuario_nuevo`        | `auth.users` AFTER INSERT                 | Crea el perfil en `usuario`                                              |
| `trg_reporte_caracteristica_validar` | `reporte_caracteristica` BEFORE INSERT | Un detalle de un tipo solo se marca en reportes de ese tipo |

### Funciones

- `es_moderador()` — SECURITY DEFINER, `search_path` fijo.
- `votar(p_id_reporte, p_sigue)` — toda la lógica de votos en un solo lugar: bloquea el reporte con
  `FOR UPDATE` (sin JOIN), valida (el autor no vota "Sigue ahí"; nadie vota en uno solucionado; error si
  vota lo mismo dos veces), guarda o cambia el voto, ajusta los dos contadores en un solo UPDATE y cambia
  el estado: 3 "sigue" → Confirmado, Alto con 5 → Prioritario, 3 "ya no está" → Solucionado.
  Devuelve el id del voto (para la foto de "ya no está").
- `editar_reporte(p_id_reporte, p_id_tipo, p_gravedad, p_descripcion, p_tamano, p_frecuencia, p_horario,
  p_caracteristicas)` — autor mientras está en Reportado, o moderador siempre; usa `FOR UPDATE`;
  no cambia código, ubicación, estado ni votos; reemplaza las características.
- `cambiar_rol(p_id_usuario, p_rol)` — solo moderador; nadie cambia su propio rol.
- `cambiar_estado(p_id_reporte, p_id_estado, p_comentario)` — solo moderador; valida la transición;
  usa `SELECT ... FOR UPDATE` para la concurrencia.

### Vistas

- `v_reporte_detalle` — reporte con nombres de tipo, estado, zona y usuario.
- `v_resumen_zona` — reportes por zona y estado (zonas con más reportes).
- `v_resumen_tipo` — reportes por tipo (problemas más frecuentes).
- `v_focos_recurrentes` — `ST_ClusterDBSCAN` (100 m, mínimo 3) en UTM 19S (EPSG:32719).
- Los resúmenes por característica y por semana de Estadísticas los calcula `consultas.py` en Python.

### Seguridad (RLS en todas las tablas)

- Leer: cualquier usuario con sesión.
- Crear reporte: solo a nombre propio.
- Votar: solo con `votar()` (confirmacion no tiene política de INSERT).
- Fotos: el autor sube las del reporte; quien votó "Ya no está" sube la de su voto.
- Editar reporte: solo con `editar_reporte()` (no hay políticas de UPDATE).
- Eliminar reporte: política DELETE — el autor mientras está en Reportado, o un moderador. Se borran en
  cascada votos, fotos, historial y características; la app borra después los archivos de Storage
  (política: solo archivos que ya no tienen fila en `evidencia`).
- Cambiar estado: solo con `cambiar_estado()`; cambiar rol: solo con `cambiar_rol()`.

### Realtime

Publicación `supabase_realtime`: `reporte`, `confirmacion`, `seguimiento`, `evidencia`.

Casos para la defensa (dos sesiones A y B):

1. A crea un reporte → B ve el marcador nuevo y una notificación.
2. A confirma o cambia el estado → B ve el cambio en el detalle y el color del marcador.
3. El mapa, el listado y el panel de B se actualizan sin recargar.

### Concurrencia (pruebas)

- Varios usuarios confirman el mismo reporte a la vez → `total_confirmaciones` correcto.
- El mismo usuario confirma dos veces a la vez → una falla ("ya votó") y la app muestra el error.
- Varios dicen "Ya no está" a la vez → los 3 primeros lo solucionan y los demás reciben error.
- Dos moderadores cambian el estado a la vez → el historial queda consistente.

---

## 6. Consideraciones éticas y de calidad de datos

- No registrar nombres, domicilios exactos, CI ni teléfonos de terceros en las descripciones.
- Las fotos se difuminan (rostros y placas con OpenCV) y se comprimen (Pillow) **antes de subirse**.
- El usuario acepta un aviso de uso responsable al registrarse.
- La base empieza vacía, solo con el admin (`09_datos_prueba.sql`). Las pruebas crean sus propias cuentas
  `@ecoalerta.test` y reportes con el prefijo `[PRUEBA]`; volver a ejecutar `09` los borra.

---

## 7. Estructura del proyecto

Estructura **simple**. No agregar archivos ni carpetas fuera de esta lista sin preguntar.

```
proyecto/
├── CLAUDE.md
├── README.md            # Cómo instalar y ejecutar
├── requirements.txt
├── .gitignore           # config.py, .nicegui/, venv/, __pycache__/
├── main.py              # Arranca la app
├── config.py            # URL y clave de Supabase (NO se sube a GitHub)
├── config_ejemplo.py    # Copia de config.py sin las claves reales
├── conexion.py          # Conexión, login y tiempo real
├── consultas.py         # Funciones que leen y guardan en la BD
├── procesamiento.py     # Fotos: difuminar y comprimir
│
├── paginas/
│   ├── login.py         # Login, registro, menú lateral y barra de arriba
│   ├── mapa.py          # Inicio (/): tarjetas y lista · Mapa (/mapa): filtros y leyenda · tarjeta con votos
│   ├── reporte.py       # Nuevo reporte, detalle (votos, historial, cambiar estado) y Mis reportes
│   └── panel.py         # Estadísticas (tipos, distritos, focos) y Usuarios (solo moderador)
│
├── sql/
│   ├── 01_extensiones.sql
│   ├── 02_tablas.sql
│   ├── 03_triggers.sql
│   ├── 04_funciones.sql
│   ├── 05_rls.sql
│   ├── 06_vistas.sql
│   ├── 07_realtime.sql
│   ├── 08_datos_catalogo.sql
│   └── 09_datos_prueba.sql
│
├── pruebas/             # CRUD, concurrencia, tiempo real, consultas
└── docs/                # Modelo ER, hallazgos, capturas
```

### Reparto por integrante

| Integrante | Archivos                                   |
| ---------- | ------------------------------------------ |
| 1          | `sql/`                                     |
| 2          | `conexion.py`, `paginas/login.py`          |
| 3          | `paginas/mapa.py`, `paginas/reporte.py`    |
| 4          | `procesamiento.py`, `paginas/panel.py`, `pruebas/` |
| Todos      | `consultas.py`                             |

---

## 8. Reglas para Claude Code

- Código, nombres y comentarios en **español**.
- **Comentarios simples, como los escribiría un estudiante**: frases cortas que expliquen qué hace el
  bloque. Nada de docstrings largos (`Args:` / `Returns:`) ni comentarios en exceso.
- Código directo y corto: sin clases ni patrones de diseño innecesarios. Escribir lo mínimo que
  funcione correctamente.
- Usar el cliente **asíncrono** de Supabase (`acreate_client`) para Realtime.
- Las claves van en `config.py` (en `.gitignore`). Nunca usar la clave `service_role` en la app.
- Los archivos SQL se ejecutan **en orden** en el SQL Editor de Supabase.
- Toda regla de negocio importante (zona, estados, conteo, unicidad) va **en la base de datos**.
- Al terminar cada cambio, explicar qué se hizo y cómo probarlo.

# Manual simple de EcoAlerta

## 1. ¿Qué hace el sistema?

EcoAlerta permite registrar focos de contaminación en El Alto. Los usuarios pueden:

- Crear reportes con ubicación, descripción, gravedad y fotografías.
- Ver los reportes en una lista y en un mapa.
- Confirmar que un problema continúa o avisar que ya no está.
- Consultar el historial de cada reporte.

Los moderadores también pueden cambiar el estado de un reporte, editar información y administrar usuarios.

La aplicación está hecha con Python y NiceGUI. Supabase se encarga de la autenticación, la base de datos, el almacenamiento de fotos y las actualizaciones en tiempo real.

## 2. Carpetas y archivos principales

### Archivos Python de la raíz

- [`main.py`](./main.py): inicia la aplicación y carga las páginas.
- [`config.py`](./config.py): contiene la URL y la clave de Supabase.
- [`conexion.py`](./conexion.py): crea la conexión de cada usuario, inicia sesión, registra usuarios y maneja los cambios en tiempo real.
- [`consultas.py`](./consultas.py): reúne las operaciones que leen o guardan información en Supabase.
- [`procesamiento.py`](./procesamiento.py): prepara las fotos antes de subirlas; difumina rostros y placas y reduce su tamaño.

### Carpeta `paginas`

- [`paginas/login.py`](./paginas/login.py): inicio de sesión, registro y menú principal.
- [`paginas/mapa.py`](./paginas/mapa.py): pantalla de inicio, mapa, lista de reportes y votos.
- [`paginas/reporte.py`](./paginas/reporte.py): formulario para crear reportes, detalle, edición y eliminación.
- [`paginas/panel.py`](./paginas/panel.py): estadísticas y funciones para moderadores.

### Carpeta `sql`

Los archivos SQL definen la estructura y las reglas de Supabase:

- `01_extensiones.sql`: instala PostGIS.
- `02_tablas.sql`: crea las tablas.
- `03_triggers.sql`: automatiza acciones al insertar o modificar datos.
- `04_funciones.sql`: contiene operaciones como votar, editar y cambiar estados.
- `05_rls.sql`: define quién puede leer, crear, editar o eliminar.
- `06_vistas.sql`: prepara consultas resumidas para el mapa y las estadísticas.
- `07_realtime.sql`: habilita actualizaciones en tiempo real.
- `08_datos_catalogo.sql`: carga tipos de contaminación, estados y características.
- `09_datos_prueba.sql`: carga o limpia datos de prueba.

## 3. Cómo inicia la aplicación

1. Se ejecuta `python main.py`.
2. [`main.py`](./main.py) importa las páginas y arranca NiceGUI.
3. El usuario entra a `/login`.
4. [`paginas/login.py`](./paginas/login.py) usa [`conexion.py`](./conexion.py) para iniciar sesión o crear una cuenta.
5. Supabase devuelve la sesión del usuario.
6. La aplicación consulta su perfil en la tabla `usuario`.
7. El usuario entra a la pantalla de inicio.

Cada navegador tiene su propio cliente de Supabase. Por eso las consultas se hacen usando la sesión del usuario actual.

## 4. Crear un nuevo reporte

La opción **Nuevo reporte** abre la ruta `/reporte/nuevo`.

Los archivos que participan son:

1. [`paginas/login.py`](./paginas/login.py) muestra el menú y permite abrir la pantalla.
2. [`paginas/reporte.py`](./paginas/reporte.py) dibuja el formulario.
3. [`consultas.py`](./consultas.py) valida los datos y realiza los llamados a Supabase.
4. [`conexion.py`](./conexion.py) ejecuta las consultas y convierte los errores en mensajes entendibles.
5. [`procesamiento.py`](./procesamiento.py) prepara las fotografías.
6. Los triggers y las tablas de `sql/` aplican las reglas finales en Supabase.

### Datos que se llenan en el formulario

El usuario selecciona:

- Tipo de contaminación.
- Nivel de gravedad.
- Tamaño del área.
- Frecuencia del problema.
- Horario, si se conoce.
- Características observadas.
- Descripción.
- Ubicación en el mapa o mediante la ubicación del dispositivo.
- Fotografías opcionales.

La ubicación es obligatoria. La descripción debe tener entre 10 y 500 caracteres.

## 5. Qué ocurre al presionar “Registrar reporte”

El flujo es el siguiente:

1. [`paginas/reporte.py`](./paginas/reporte.py) reúne los datos del formulario.
2. Llama a `consultas.crear_reporte(...)`.
3. [`consultas.py`](./consultas.py) revisa rápidamente los campos.
4. Se inserta una fila en la tabla `reporte`.
5. La base de datos completa automáticamente varios datos mediante un trigger.
6. Si hay características seleccionadas, se insertan en `reporte_caracteristica`.
7. Si hay fotos, se procesan y se suben al bucket `evidencias`.
8. La ruta de cada foto se registra en la tabla `evidencia`.
9. La aplicación muestra el código generado, por ejemplo `REP-2026-000001`.
10. El usuario es enviado al detalle del reporte.

## 6. Tablas afectadas al guardar un reporte

### Tabla `reporte`

Es la tabla principal. Guarda:

- Código del reporte.
- Usuario que lo creó.
- Tipo y gravedad.
- Descripción.
- Tamaño, frecuencia y horario.
- Latitud y longitud.
- Estado actual.
- Contadores de confirmaciones.
- Fecha de creación.

El usuario no tiene que escribir el código, la zona ni el estado inicial. El trigger `fn_reporte_preparar`, definido en `sql/03_triggers.sql`, hace lo siguiente:

- Crea el punto geográfico.
- Busca la zona de El Alto donde está el punto.
- Genera el código del reporte.
- Coloca el estado inicial en `Reportado`.
- Inicializa los contadores en cero.

Si la ubicación no pertenece a ninguna zona configurada, el reporte no se guarda.

### Tabla `seguimiento`

Cuando se crea el reporte, el trigger `fn_reporte_seguimiento` registra el primer movimiento:

- Estado nuevo: `Reportado`.
- Comentario: `Reporte registrado`.
- Usuario que creó el reporte.

Esta tabla sirve para mostrar el historial del reporte.

### Tabla `reporte_caracteristica`

Se crea una fila por cada característica marcada en el formulario.

Por ejemplo, un reporte puede tener las características “Cerca de una escuela” y “Malos olores”.

La base de datos verifica que una característica específica corresponda al tipo de contaminación seleccionado.

### Bucket `evidencias` y tabla `evidencia`

La fotografía no se guarda directamente dentro de la tabla. El proceso es:

1. [`procesamiento.py`](./procesamiento.py) difumina rostros y placas.
2. La imagen se sube al bucket privado `evidencias` de Supabase Storage.
3. La tabla `evidencia` guarda la ruta del archivo y el reporte al que pertenece.

La aplicación utiliza URLs temporales para mostrar las fotos.

## 7. Estados de un reporte

Los estados principales son:

1. `Reportado`: acaba de registrarse.
2. `Confirmado`: al menos tres vecinos indicaron que el problema continúa.
3. `Prioritario`: un reporte de gravedad alta recibió al menos cinco confirmaciones.
4. `En atención`: un moderador empezó a atenderlo.
5. `Solucionado`: el problema fue resuelto o tres vecinos indicaron que ya no está.

El orden y los nombres están en la tabla `estado`.

## 8. Qué ocurre cuando un vecino vota

Los botones están en [`paginas/mapa.py`](./paginas/mapa.py). La operación pasa por:

1. `paginas/mapa.py`.
2. `consultas.votar(...)` en [`consultas.py`](./consultas.py).
3. La función `votar(...)` de `sql/04_funciones.sql`.

La función de la base de datos:

- Guarda el voto en `confirmacion`.
- Evita que un usuario vote dos veces de la misma manera.
- Actualiza los contadores de `reporte`.
- Puede cambiar automáticamente el estado.

Un usuario no puede confirmar su propio reporte. Cuando el usuario indica que el problema ya no está, puede adjuntar una fotografía. Esa fotografía se guarda en `evidencia` relacionada con el voto.

## 9. Ver un reporte

La lista y el mapa se construyen principalmente desde [`paginas/mapa.py`](./paginas/mapa.py).

La información se obtiene desde la vista `v_reporte_detalle`, que reúne datos de varias tablas:

- `reporte`
- `tipo_contaminacion`
- `estado`
- `zona`
- `usuario`

Al abrir el detalle, [`paginas/reporte.py`](./paginas/reporte.py) consulta también:

- Las características marcadas.
- Las fotografías.
- Los votos.
- El historial en `seguimiento`.

## 10. Editar un reporte

La edición se inicia desde el detalle del reporte.

El flujo es:

1. [`paginas/reporte.py`](./paginas/reporte.py) abre el formulario de edición.
2. [`consultas.py`](./consultas.py) llama a la función `editar_reporte`.
3. La función de `sql/04_funciones.sql` verifica los permisos.
4. Se actualizan los datos permitidos en `reporte`.
5. Se reemplazan las filas de `reporte_caracteristica`.

El autor solo puede editar mientras el reporte está en `Reportado`. Un moderador puede editarlo en cualquier momento. La ubicación, el código, el estado, los votos y la fecha no se cambian desde esta opción.

## 11. Eliminar un reporte

Al eliminar un reporte:

1. [`paginas/reporte.py`](./paginas/reporte.py) pide confirmación.
2. [`consultas.py`](./consultas.py) elimina la fila de `reporte`.
3. La base de datos elimina en cascada sus votos, fotos registradas, historial y características.
4. Las fotografías se eliminan del bucket `evidencias`.

El autor puede eliminar su reporte mientras está en `Reportado`. Un moderador también puede hacerlo.

## 12. Qué puede hacer un moderador

Las funciones de moderación se muestran principalmente en [`paginas/panel.py`](./paginas/panel.py) y en el detalle del reporte.

Un moderador puede:

- Cambiar un reporte a `Prioritario`, `En atención` o `Solucionado`.
- Escribir un comentario al cambiar el estado.
- Editar o eliminar reportes.
- Cambiar el rol de un usuario.
- Eliminar cuentas de vecinos. Esto también elimina sus reportes, votos y fotos.
- Consultar estadísticas.

Cuando un moderador cambia el estado:

1. La página llama a `consultas.cambiar_estado(...)`.
2. [`consultas.py`](./consultas.py) llama a la función `cambiar_estado` de Supabase.
3. La función verifica que el usuario sea moderador.
4. Se actualiza `reporte`.
5. El trigger agrega el cambio a `seguimiento`.

Para marcar un reporte como `Solucionado`, el comentario es obligatorio.

## 13. Actualización en tiempo real

[`conexion.py`](./conexion.py) escucha cambios en estas tablas:

- `reporte`
- `confirmacion`
- `seguimiento`
- `evidencia`

Cuando otro usuario vota, sube una foto o un moderador cambia el estado, la página recibe el cambio y se actualiza sin tener que recargarla manualmente.

## 14. Resumen rápido del recorrido

```text
Usuario
  ↓
paginas/reporte.py
  ↓
consultas.py
  ↓
conexion.py
  ↓
Supabase
  ↓
triggers y funciones SQL
  ↓
reporte, seguimiento, reporte_caracteristica,
evidencia y Storage
```

La regla más importante es que la interfaz muestra formularios y botones, pero la base de datos es la que confirma los permisos, valida los datos, calcula la zona y controla los cambios de estado.

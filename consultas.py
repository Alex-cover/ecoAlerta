# Funciones que leen y guardan en la base de datos.
# Todas reciben el cliente del usuario: reportes = await listar_reportes(cliente, filtros)
# Las reglas (zona, estados, conteo, no confirmar dos veces) las cumple la base de datos.

import uuid
from datetime import datetime, timedelta, timezone

from conexion import ErrorBD, ejecutar, mensaje_error

# Id de los estados (ver sql/08_datos_catalogo.sql)
REPORTADO, CONFIRMADO, PRIORITARIO, EN_ATENCION, SOLUCIONADO = 1, 2, 3, 4, 5
GRAVEDADES = ["Bajo", "Medio", "Alto"]
# Los mismos valores que los CHECK de la tabla reporte.
TAMANOS = ["Pequeño", "Mediano", "Grande"]
FRECUENCIAS = ["Primera vez", "A veces", "Todos los días", "Permanente"]
HORARIOS = ["Mañana", "Tarde", "Noche"]

# Bolivia está en UTC-4 todo el año.
HORA_BOLIVIA = timezone(timedelta(hours=-4))


def formato_fecha(texto):
    """'2026-10-21T18:30:00+00:00' -> '21/10/2026 14:30' (hora de Bolivia)."""
    fecha = datetime.fromisoformat(texto)
    return fecha.astimezone(HORA_BOLIVIA).strftime("%d/%m/%Y %H:%M")


def es_de_hoy(texto):
    """¿La fecha cae hoy (en Bolivia)?"""
    return datetime.fromisoformat(texto).astimezone(HORA_BOLIVIA).date() == datetime.now(HORA_BOLIVIA).date()


async def mi_id(cliente):
    sesion = await cliente.auth.get_session()
    return sesion.user.id


# Catálogos.

async def opciones(cliente, tabla, id_columna):
    """Catálogo como {id: nombre}, listo para un ui.select."""
    filas = await ejecutar(cliente.table(tabla).select("*").order(id_columna))
    return {f[id_columna]: f["nombre"] for f in filas}


async def tipos(cliente):
    """Tipos de contaminación con su color y su ícono."""
    return await ejecutar(cliente.table("tipo_contaminacion").select("*").order("id_tipo"))


async def caracteristicas(cliente):
    """Catálogo de características (generales y de cada tipo)."""
    return await ejecutar(cliente.table("caracteristica").select("*").order("id_caracteristica"))


async def zonas_con_poligono(cliente):
    # Supabase devuelve la geometría como GeoJSON.
    return await ejecutar(cliente.table("zona").select("nombre, geom"))


# Reportes (CRUD)
# C crear_reporte · R ver_reporte / listar_reportes · U editar_reporte · D eliminar_reporte.
# Quién puede editar o eliminar lo decide la base de datos (editar_reporte() y la política RLS de DELETE).

def revisar_datos(datos):
    """Revisiones rápidas antes de mandar a la BD (la BD igual las vuelve a revisar con CHECK)."""
    if len((datos.get("descripcion") or "").strip()) < 10:
        raise ErrorBD("La descripción debe tener al menos 10 caracteres.")
    if not datos.get("id_tipo") or not datos.get("gravedad"):
        raise ErrorBD("Elija el tipo y la gravedad.")
    if not datos.get("tamano") or not datos.get("frecuencia"):
        raise ErrorBD("Indique el tamaño del área y cada cuánto pasa.")


# C: crear.
async def crear_reporte(cliente, datos, caracteristicas=()):
    """Guarda un reporte y las características marcadas. Los triggers ponen el código, la zona y el estado."""
    revisar_datos(datos)
    if datos.get("latitud") is None:
        raise ErrorBD("Marque la ubicación en el mapa.")
    filas = await ejecutar(cliente.table("reporte").insert(datos))
    nuevo = filas[0]
    if caracteristicas:
        await ejecutar(cliente.table("reporte_caracteristica").insert(
            [{"id_reporte": nuevo["id_reporte"], "id_caracteristica": c} for c in caracteristicas]))
    return nuevo


# R: ver uno y listar.
async def ver_reporte(cliente, id_reporte):
    """Un reporte con los nombres de tipo, estado, distrito y autor."""
    return await ejecutar(cliente.table("v_reporte_detalle").select("*").eq("id_reporte", id_reporte).single())


async def listar_reportes(cliente, filtros={}):
    """Reportes de v_reporte_detalle con filtros por fecha, tipo, estado, gravedad, distrito y autor."""
    consulta = cliente.table("v_reporte_detalle").select("*")
    if filtros.get("desde"):
        consulta = consulta.gte("fecha_creacion", filtros["desde"] + "T00:00:00-04:00")
    if filtros.get("hasta"):
        consulta = consulta.lte("fecha_creacion", filtros["hasta"] + "T23:59:59-04:00")
    # Los demás filtros son por igualdad y solo se aplican si tienen valor.
    for columna in ("id_tipo", "id_estado", "gravedad", "id_zona", "id_usuario"):
        if filtros.get(columna):
            consulta = consulta.eq(columna, filtros[columna])
    return await ejecutar(consulta.order("fecha_creacion", desc=True))


async def caracteristicas_de(cliente, id_reporte):
    """Características marcadas en un reporte: [{"id_caracteristica", "grupo", "nombre"}]."""
    filas = await ejecutar(cliente.table("reporte_caracteristica")
                           .select("id_caracteristica, caracteristica(grupo, nombre)")
                           .eq("id_reporte", id_reporte).order("id_caracteristica"))
    return [{"id_caracteristica": f["id_caracteristica"], **f["caracteristica"]} for f in filas]


# U: editar.
async def editar_reporte(cliente, id_reporte, datos, caracteristicas=()):
    """Cambia tipo, gravedad, descripción, tamaño, frecuencia, horario y características.
    Autor (si está en Reportado) o moderador; la ubicación y el estado no se editan aquí."""
    revisar_datos(datos)
    await ejecutar(cliente.rpc("editar_reporte", {
        "p_id_reporte": id_reporte, "p_id_tipo": datos["id_tipo"], "p_gravedad": datos["gravedad"],
        "p_descripcion": datos["descripcion"], "p_tamano": datos["tamano"], "p_frecuencia": datos["frecuencia"],
        "p_horario": datos.get("horario"), "p_caracteristicas": list(caracteristicas)}))


# D: eliminar.
async def eliminar_reporte(cliente, id_reporte):
    """Autor (si está en Reportado) o moderador. En cascada se borran votos, fotos, historial y características."""
    fotos = await ejecutar(cliente.table("evidencia").select("ruta_archivo").eq("id_reporte", id_reporte))
    filas = await ejecutar(cliente.table("reporte").delete().eq("id_reporte", id_reporte))
    # Si RLS no lo permite, no da error: simplemente no borra nada.
    if not filas:
        raise ErrorBD("Solo el autor (mientras está en Reportado) o un moderador puede eliminar este reporte.")
    # Los archivos se borran de Storage al final, cuando ya no pertenecen a ningún reporte.
    if fotos:
        await cliente.storage.from_("evidencias").remove([f["ruta_archivo"] for f in fotos])


def puede_editar(perfil, r):
    """Para mostrar u ocultar los botones; la BD igual lo vuelve a revisar."""
    return perfil["rol"] == "moderador" or (r["id_usuario"] == perfil["id_usuario"] and r["id_estado"] == REPORTADO)


# Votos.

async def votar(cliente, id_reporte, sigue):
    """sigue=True "Sigue ahí", sigue=False "Ya no está". Devuelve el id del voto."""
    # Si ya votó lo contrario se cambia su voto; las reglas las revisa la base de datos.
    return await ejecutar(cliente.rpc("votar", {"p_id_reporte": id_reporte, "p_sigue": sigue}))


async def mi_voto(cliente, id_reporte):
    """True, False o None si todavía no votó."""
    filas = await ejecutar(cliente.table("confirmacion").select("sigue")
                           .eq("id_reporte", id_reporte).eq("id_usuario", await mi_id(cliente)))
    return filas[0]["sigue"] if filas else None


# Seguimiento.

async def historial(cliente, id_reporte):
    """Historial de estados con nombres, del más viejo al más nuevo."""
    return await ejecutar(
        cliente.table("seguimiento")
        # Traemos los nombres de los estados y del usuario usando las claves foráneas.
        .select("fecha, comentario, id_estado_anterior, id_estado_nuevo, "
                "anterior:estado!fk_seguimiento_estado_anterior(nombre), "
                "nuevo:estado!fk_seguimiento_estado_nuevo(nombre), usuario(nombre_usuario)")
        .eq("id_reporte", id_reporte).order("fecha").order("id_seguimiento")
    )


async def cambiar_estado(cliente, id_reporte, id_estado, comentario=""):
    """Solo moderador. La función de la BD valida la transición."""
    await ejecutar(cliente.rpc("cambiar_estado", {
        "p_id_reporte": id_reporte, "p_id_estado": id_estado, "p_comentario": comentario,
    }))


# Usuarios.

async def usuarios(cliente):
    """Usuarios con la cantidad de reportes que hizo cada uno."""
    filas = await ejecutar(cliente.table("usuario")
                           .select("id_usuario, nombre_usuario, nombre_completo, rol, fecha_registro, reporte(count)")
                           .order("fecha_registro"))
    for f in filas:
        f["reportes"] = f.pop("reporte")[0]["count"]
    return filas


async def cambiar_rol(cliente, id_usuario, rol):
    """Solo moderador. rol = 'estudiante' o 'moderador'."""
    await ejecutar(cliente.rpc("cambiar_rol", {"p_id_usuario": id_usuario, "p_rol": rol}))


async def eliminar_usuario(cliente, id_usuario):
    """Solo moderador. Elimina la cuenta, sus datos relacionados y sus fotos."""
    reportes = await ejecutar(cliente.table("reporte").select("id_reporte").eq("id_usuario", id_usuario))
    ids_reportes = [r["id_reporte"] for r in reportes]
    fotos = []
    if ids_reportes:
        fotos = await ejecutar(cliente.table("evidencia").select("ruta_archivo")
                               .in_("id_reporte", ids_reportes))
    votos = await ejecutar(cliente.table("confirmacion").select("id_confirmacion")
                           .eq("id_usuario", id_usuario))
    ids_votos = [v["id_confirmacion"] for v in votos]
    if ids_votos:
        fotos += await ejecutar(cliente.table("evidencia").select("ruta_archivo")
                                .in_("id_confirmacion", ids_votos))
    await ejecutar(cliente.rpc("eliminar_usuario", {"p_id_usuario": id_usuario}))
    if fotos:
        await cliente.storage.from_("evidencias").remove([f["ruta_archivo"] for f in fotos])


# Fotos.

async def subir_foto(cliente, id_reporte, contenido, id_confirmacion=None):
    """Sube una foto JPG (ya difuminada) al bucket y la registra en la tabla evidencia."""
    # Con id_confirmacion es la foto de que el problema ya no está.
    ruta = f"{await mi_id(cliente)}/{id_reporte}/{uuid.uuid4().hex}.jpg"
    try:
        await cliente.storage.from_("evidencias").upload(ruta, contenido, {"content-type": "image/jpeg"})
    except Exception as e:
        raise mensaje_error(e) from e
    await ejecutar(cliente.table("evidencia").insert(
        {"id_reporte": id_reporte, "ruta_archivo": ruta, "id_confirmacion": id_confirmacion}))


async def urls_fotos(cliente, id_reporte, ya_no_esta=False):
    """URLs firmadas (válidas 1 hora) de las fotos de un reporte; el bucket es privado."""
    # ya_no_esta=True trae las fotos de que el problema ya no está.
    consulta = cliente.table("evidencia").select("ruta_archivo").eq("id_reporte", id_reporte)
    if ya_no_esta:
        consulta = consulta.not_.is_("id_confirmacion", "null")
    else:
        consulta = consulta.is_("id_confirmacion", "null")
    fotos = await ejecutar(consulta.order("fecha_subida"))
    if not fotos:
        return []
    urls = await cliente.storage.from_("evidencias").create_signed_urls([f["ruta_archivo"] for f in fotos], 3600)
    return [u["signedURL"] for u in urls]


# Consultas de análisis (vistas)

async def resumen_tipo(cliente):
    return await ejecutar(cliente.table("v_resumen_tipo").select("*").order("total", desc=True))


async def resumen_zona(cliente):
    return await ejecutar(cliente.table("v_resumen_zona").select("*").order("total", desc=True))


async def focos_recurrentes(cliente):
    return await ejecutar(cliente.table("v_focos_recurrentes").select("*").order("total_reportes", desc=True))


async def reportes_por_semana(cliente):
    """Reportes nuevos por semana (lunes, hora de Bolivia): [{"semana": "2026-10-19", "total": 4}, ...]"""
    conteo = {}
    for r in await listar_reportes(cliente):
        dia = datetime.fromisoformat(r["fecha_creacion"]).astimezone(HORA_BOLIVIA).date()
        lunes = (dia - timedelta(days=dia.weekday())).isoformat()
        conteo[lunes] = conteo.get(lunes, 0) + 1
    return [{"semana": s, "total": n} for s, n in sorted(conteo.items())]


async def resumen_caracteristica(cliente):
    """Cuántos reportes tienen cada característica (solo las que aparecen en algún reporte)."""
    filas = await ejecutar(cliente.table("reporte_caracteristica").select(
        "id_caracteristica, caracteristica(grupo, nombre, tipo_contaminacion(nombre)), reporte(gravedad, id_estado)"))
    resumen = {}
    for f in filas:
        c = f["caracteristica"]
        if f["id_caracteristica"] not in resumen:
            tipo = c["tipo_contaminacion"]["nombre"] if c["tipo_contaminacion"] else None
            resumen[f["id_caracteristica"]] = {"grupo": c["grupo"], "caracteristica": c["nombre"], "tipo": tipo,
                                               "total": 0, "gravedad_alta": 0, "sin_solucionar": 0}
        fila = resumen[f["id_caracteristica"]]
        fila["total"] += 1
        fila["gravedad_alta"] += f["reporte"]["gravedad"] == "Alto"
        fila["sin_solucionar"] += f["reporte"]["id_estado"] != SOLUCIONADO
    return sorted(resumen.values(), key=lambda x: x["total"], reverse=True)

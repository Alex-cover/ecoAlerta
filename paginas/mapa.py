# Inicio (/): tarjetas con totales y lista de reportes. Mapa (/mapa): pines con filtros y leyenda.
# Aquí también está la tarjeta de un reporte con sus votos (se usa en el mapa y en el detalle).

import base64
import json
from contextlib import nullcontext

from nicegui import ui

import conexion
import consultas
import procesamiento
from conexion import ErrorBD
from paginas.login import encabezado, revisar_sesion

CENTRO = (-16.505, -68.19)  # centro de El Alto.

COLOR_ESTADO = {1: "#757575", 2: "#1565C0", 3: "#C62828", 4: "#EF6C00", 5: "#2E7D32"}
COLOR_GRAVEDAD = {"Bajo": "#2e9e5b", "Medio": "#e0a800", "Alto": "#d32f2f"}


OSM_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors"
)

def crear_mapa(centro, zoom, clases):
    """Crea un mapa Leaflet usando explícitamente las teselas de OpenStreetMap."""
    mapa = ui.leaflet(center=centro, zoom=zoom).classes(clases)
    if mapa.layers:
        mapa.remove_layer(mapa.layers[0])
    mapa.tile_layer(
        url_template=OSM_URL,
        options={"attribution": OSM_ATRIBUTION},
    )
    return mapa


def agregar_marcador(mapa, r, clic=True):
    """Pin con el color y el ícono del tipo; el borde es el color del estado."""
    html = (f'<div style="width:34px;height:34px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
            f'background:{r["color"]};border:3px solid {COLOR_ESTADO[r["id_estado"]]};'
            f'box-shadow:0 2px 5px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center">'
            f'<i class="material-icons" style="transform:rotate(45deg);color:white;font-size:18px">'
            f'{r["icono"]}</i></div>')
    icono = {"html": html, "className": "", "iconSize": [34, 34], "iconAnchor": [17, 42]}
    capa = mapa.marker(latlng=(r["latitud"], r["longitud"]))
    # Los métodos con ":" reciben código JavaScript.
    capa.run_method(":setIcon", f"L.divIcon({json.dumps(icono)})")
    if clic:
        # Al hacer clic avisamos a Python con un evento (ver ui.on("abrir_reporte") abajo)
        capa.run_method(":on", "'click'", f"() => emitEvent('abrir_reporte', {r['id_reporte']})")
    return capa


def etiqueta(texto, color):
    ui.badge(texto).props("rounded").style(f"background:{color} !important; padding:4px 10px")


def icono_tipo(r, tamano=40):
    with ui.element("div").classes("rounded-full flex items-center justify-center shrink-0") \
            .style(f"background:{r['color']}; width:{tamano}px; height:{tamano}px"):
        ui.icon(r["icono"], color="white", size=f"{tamano // 2 + 2}px")


# Votos.

def pedir_ya_no_esta(cliente, r, al_cambiar):
    """Ventana para avisar que el problema ya no está, con una foto opcional."""
    foto = {}
    enviando = False
    captura = {}

    async def obtener_captura():
        return await ui.run_javascript("""
            new Promise(resolve => navigator.geolocation.getCurrentPosition(
                p => resolve({latitud: p.coords.latitude, longitud: p.coords.longitude,
                              precision: p.coords.accuracy}),
                () => resolve(null), {enableHighAccuracy: true, timeout: 10000}))
        """, timeout=15)

    async def foto_subida(e):
        try:
            foto["contenido"], cantidad = procesamiento.preparar_foto(e.content.read())
        except Exception:
            ui.notify("El archivo no es una imagen válida", type="negative")
            return
        ubicacion = await obtener_captura()
        if ubicacion:
            captura.update(ubicacion)
        else:
            ui.notify("La foto quedará sin verificación de ubicación.", type="warning")
        if cantidad:
            ui.notify(f"Se difuminaron {cantidad} rostro(s) o placa(s)")
        vista.clear()
        with vista:
            ui.image("data:image/jpeg;base64," + base64.b64encode(foto["contenido"]).decode()).classes("w-40 rounded")

    async def enviar():
        nonlocal enviando
        if enviando:
            return
        enviando = True
        boton_enviar.disable()
        try:
            id_voto = await consultas.votar(cliente, r["id_reporte"], False)
            if foto:
                await consultas.subir_foto(
                    cliente, r["id_reporte"], foto["contenido"], id_voto,
                    captura.get("latitud"), captura.get("longitud"), captura.get("precision"))
        except ErrorBD as e:
            enviando = False
            boton_enviar.enable()
            ui.notify(str(e), type="warning")
            return
        dialogo.close()
        ui.notify("Gracias por avisar", type="positive")

    with ui.dialog() as dialogo, ui.card().style("width: min(420px, 92vw)"):
        ui.label("¿El problema ya no está?").classes("text-h6")
        ui.label("Si puede, suba una foto de cómo está el lugar ahora (se difuminan rostros y placas). "
                 "Con 3 vecinos que digan que ya no está, el reporte pasa a Solucionado.").classes("text-caption")
        vista = ui.row()
        ui.upload(auto_upload=True, max_files=1, on_upload=foto_subida) \
            .props('accept="image/*" capture="environment" label="Tomar o subir foto (opcional)" flat bordered') \
            .classes("w-full")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            boton_enviar = ui.button("Enviar", icon="close", color="negative", on_click=enviar)
    dialogo.open()


async def votos(cliente, perfil, r, al_cambiar):
    """Contadores y botones "Sigue ahí" / "Ya no está". al_cambiar() vuelve a dibujar."""
    votando = False
    with ui.row().classes("items-center gap-4"):
        ui.label("Votos:").classes("text-weight-medium")
        with ui.row().classes("items-center gap-1"):
            ui.icon("thumb_up", color="positive")
            ui.label(f"{r['total_confirmaciones']} sigue ahí")
        with ui.row().classes("items-center gap-1"):
            ui.icon("thumb_down", color="negative")
            ui.label(f"{r['total_ya_no_esta']} ya no está")

    if r["es_final"]:
        ui.label("Reporte solucionado: ya no recibe votos.").classes("text-positive")
        return

    async def sigue():
        nonlocal votando
        if votando:
            return
        votando = True
        boton_sigue.disable()
        boton_no.disable()
        try:
            await consultas.votar(cliente, r["id_reporte"], True)
            ui.notify("Gracias por confirmar", type="positive")
        except ErrorBD as e:
            votando = False
            boton_sigue.enable()
            boton_no.enable()
            ui.notify(str(e), type="warning")
            return

    mio = await consultas.mi_voto(cliente, r["id_reporte"])

    async def quitar():
        try:
            await consultas.quitar_voto(cliente, r["id_reporte"])
            ui.notify("Voto eliminado", type="positive")
        except ErrorBD as e:
            ui.notify(str(e), type="warning")

    with ui.row().classes("w-full no-wrap"):
        boton_sigue = ui.button("Sigue ahí", icon="check_circle", on_click=sigue).classes("grow")
        boton_no = ui.button("Ya no está", icon="cancel", color="negative",
                             on_click=lambda: pedir_ya_no_esta(cliente, r, al_cambiar)).classes("grow")

    # La base de datos revisa todo; aquí solo desactivamos lo que no se puede.
    if r["id_usuario"] == perfil["id_usuario"]:
        boton_sigue.disable()
        ui.label("Es su reporte: lo confirman otros vecinos. Puede avisar si ya no está.").classes("text-caption")
    if mio is True:
        boton_sigue.disable()
        ui.label("Usted votó que sigue ahí. Si lo limpian, puede cambiar su voto.").classes("text-caption")
    elif mio is False:
        boton_no.disable()
        ui.label("Usted votó que ya no está.").classes("text-caption")
    if mio is not None:
        ui.button("Quitar mi voto", icon="delete", on_click=quitar).props("flat no-caps")


async def tarjeta_reporte(cliente, perfil, id_reporte, al_cambiar, compacta=False):
    """Datos del reporte con su foto y sus votos. Devuelve el reporte."""
    r = await consultas.ver_reporte(cliente, id_reporte)

    with ui.row().classes("items-center no-wrap q-pa-md w-full"):
        icono_tipo(r)
        with ui.column().classes("gap-0"):
            ui.label(r["tipo"]).classes("text-h6")
            ui.label(r["codigo"]).classes("text-caption text-grey-7")

    # En la ventana del mapa mostramos la primera foto a la izquierda.
    contenedor_info = nullcontext()
    if compacta:
        fotos = await consultas.urls_fotos(cliente, id_reporte)
        if fotos:
            contenedor = ui.row().classes("w-full items-start no-wrap q-px-sm")
            with contenedor:
                ui.image(fotos[0]).classes("w-40 h-40 shrink-0 bg-grey-2 rounded-borders").props("fit=contain")
                contenedor_info = ui.column().classes("grow min-w-0")

    with contenedor_info:
        with ui.grid(columns="auto 1fr").classes("q-px-md w-full items-center gap-x-4 gap-y-2"):
            ui.label("Gravedad:").classes("text-weight-medium")
            ui.label(r["gravedad"]).classes("text-weight-bold").style(f"color:{COLOR_GRAVEDAD[r['gravedad']]}")
            ui.label("Tamaño:").classes("text-weight-medium")
            ui.label(r["tamano"])
            ui.label("Frecuencia:").classes("text-weight-medium")
            ui.label(r["frecuencia"] + (f" · {r['horario']}" if r["horario"] else ""))
            ui.label("Estado:").classes("text-weight-medium")
            with ui.element("div"):
                etiqueta(r["estado"], COLOR_ESTADO[r["id_estado"]])
            ui.label("Fecha:").classes("text-weight-medium")
            ui.label(consultas.formato_fecha(r["fecha_creacion"]))
            ui.label("Ubicación:").classes("text-weight-medium")
            ui.label(f"{r['zona']}, El Alto")
            ui.label("Reportado por:").classes("text-weight-medium")
            ui.label(r["nombre_usuario"])
        with ui.column().classes("q-px-md w-full gap-0"):
            ui.label("Descripción:").classes("text-weight-medium")
            ui.label(r["descripcion"])

        # Características marcadas, agrupadas ("Detalle", "Cerca de", "Efectos")
        marcadas = await consultas.caracteristicas_de(cliente, id_reporte)
        if marcadas:
            with ui.column().classes("q-px-md q-pt-sm w-full gap-1"):
                for grupo, titulo in (("Detalle", "Qué se ve:"), ("Cerca de", "Cerca de:"), ("Efectos", "Efectos:")):
                    nombres = [c["nombre"] for c in marcadas if c["grupo"] == grupo]
                    if nombres:
                        with ui.row().classes("items-center gap-1"):
                            ui.label(titulo).classes("text-weight-medium q-mr-xs")
                            for nombre in nombres:
                                ui.chip(nombre).props("dense outline color=primary")

        ui.separator().classes("q-mt-sm")
        with ui.column().classes("q-pa-md w-full"):
            await votos(cliente, perfil, r, al_cambiar)
            if compacta:
                ui.link("Ver historial completo", f"/reporte/{id_reporte}")
    return r


# Lista de reportes (Inicio y Mis reportes)

def tabla_reportes():
    """Tabla con ícono del tipo, etiquetas de color, votos y botón para ver el detalle."""
    columnas = [{"name": c, "label": t, "field": c, "align": "left", "sortable": True} for c, t in
                [("codigo", "Código"), ("tipo", "Tipo"), ("zona", "Distrito"), ("gravedad", "Gravedad"),
                 ("estado", "Estado"), ("fecha", "Fecha"), ("votos", "Votos"), ("acciones", "")]]
    tabla = ui.table(columns=columnas, rows=[], row_key="id_reporte", pagination=10).classes("w-full")
    tabla.add_slot("body-cell-tipo", """<q-td :props="props">
        <q-icon :name="props.row.icono" :style="{color: props.row.color}" size="22px" class="q-mr-sm"/>
        {{ props.value }}</q-td>""")
    tabla.add_slot("body-cell-gravedad", """<q-td :props="props">
        <q-badge rounded :label="props.value" :style="{background: props.row.color_gravedad, padding: '4px 10px'}"/>
        </q-td>""")
    tabla.add_slot("body-cell-estado", """<q-td :props="props">
        <q-badge rounded :label="props.value" :style="{background: props.row.color_estado, padding: '4px 10px'}"/>
        </q-td>""")
    tabla.add_slot("body-cell-votos", """<q-td :props="props">
        <q-icon name="thumb_up" color="positive" size="16px"/> {{ props.row.total_confirmaciones }}
        <q-icon name="thumb_down" color="negative" size="16px" class="q-ml-sm"/> {{ props.row.total_ya_no_esta }}
        </q-td>""")
    tabla.add_slot("body-cell-acciones", """<q-td :props="props">
        <q-btn flat round dense icon="visibility" color="primary" :href="'/reporte/' + props.row.id_reporte"/>
        </q-td>""")
    return tabla


def preparar_filas(reportes):
    """Agrega la fecha en hora de Bolivia y los colores que usa la tabla."""
    for r in reportes:
        r["fecha"] = consultas.formato_fecha(r["fecha_creacion"])
        r["color_gravedad"] = COLOR_GRAVEDAD[r["gravedad"]]
        r["color_estado"] = COLOR_ESTADO[r["id_estado"]]
    return reportes


def avisar_cambios(cambios):
    """Notificaciones de tiempo real: reporte nuevo, cambio de estado o reporte eliminado."""
    for c in cambios:
        if c["tabla"] == "reporte" and c["tipo"] == "DELETE":
            ui.notify("Se eliminó un reporte", type="info")
        if c["tabla"] == "reporte" and c["tipo"] == "INSERT":
            ui.notify(f"Nuevo reporte {c['nuevo']['codigo']}", type="info")
        if c["tabla"] == "reporte" and c["tipo"] == "UPDATE" and c["nuevo"]["id_estado"] != c["viejo"].get("id_estado"):
            ui.notify(f"{c['nuevo']['codigo']} cambió de estado", type="info")


# Inicio (/)

@ui.page("/")
async def pagina_inicio():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Inicio", "/")

    # Tarjetas con totales.
    @ui.refreshable
    def tarjetas(todos):
        pendientes = [r for r in todos if r["id_estado"] in (consultas.REPORTADO, consultas.CONFIRMADO,
                                                                consultas.PRIORITARIO)]
        datos = [("description", "Reportes hoy", sum(consultas.es_de_hoy(r["fecha_creacion"]) for r in todos), "#2563eb", "#eaf1ff"),
                 ("schedule", "Pendientes", len(pendientes), "#d97706", "#fff6e0"),
                 ("engineering", "En atención", sum(r["id_estado"] == consultas.EN_ATENCION for r in todos), "#dc2626", "#fdecec"),
                 ("check_circle", "Solucionados", sum(r["id_estado"] == consultas.SOLUCIONADO for r in todos), "#16a34a", "#e8f7ee")]
        with ui.row().classes("w-full gap-4"):
            for icono, texto, valor, color, fondo in datos:
                with ui.card().classes("grow q-pa-md").style(f"background:{fondo}; min-width:160px"):
                    with ui.row().classes("items-center no-wrap"):
                        ui.icon(icono, size="32px").style(f"color:{color}")
                        with ui.column().classes("gap-0"):
                            ui.label(texto).classes("text-grey-8")
                            ui.label(str(valor)).classes("text-h5 text-weight-bold")

    tarjetas([])

    # Lista de todos los reportes.
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center"):
            ui.label("Lista de reportes ambientales").classes("text-h6")
            ui.space()
            ui.button("Ver en el mapa", icon="map", on_click=lambda: ui.navigate.to("/mapa")).props("outline")
            ui.button("Nuevo reporte", icon="add", on_click=lambda: ui.navigate.to("/reporte/nuevo"))
        tabla = tabla_reportes()

    async def actualizar():
        reportes = await consultas.listar_reportes(cliente)
        tabla.rows = preparar_filas(reportes)
        tarjetas.refresh(reportes)

    await actualizar()

    # Tiempo real.
    async def al_cambiar(cambios):
        avisar_cambios(cambios)
        await actualizar()

    await conexion.escuchar_cambios(cliente, al_cambiar)


# Mapa (/mapa)

@ui.page("/mapa")
async def pagina_mapa():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Mapa en tiempo real", "/mapa")
    tipos = await consultas.tipos(cliente)
    estados = await consultas.opciones(cliente, "estado", "id_estado")

    # Mapa, filtros y leyenda.
    with ui.row().classes("w-full gap-4 items-stretch flex-wrap lg:flex-nowrap"):
        with ui.card().classes("grow q-pa-none overflow-hidden").style("min-width: 300px"):
            mapa = crear_mapa(CENTRO, 13, "w-full h-[78vh]")

        with ui.card().classes("w-full lg:w-72"):
            ui.label("Filtros").classes("text-subtitle1 text-weight-bold")
            tipo = ui.select({t["id_tipo"]: t["nombre"] for t in tipos}, label="Tipo de contaminación",
                             clearable=True).props("outlined dense").classes("w-full")
            gravedad = ui.select(consultas.GRAVEDADES, label="Nivel de gravedad", clearable=True) \
                .props("outlined dense").classes("w-full")
            estado = ui.select(estados, label="Estado", clearable=True).props("outlined dense").classes("w-full")
            zona = ui.select(await consultas.opciones(cliente, "zona", "id_zona"), label="Distrito",
                             clearable=True).props("outlined dense").classes("w-full")
            with ui.row().classes("w-full no-wrap"):
                desde = ui.input("Desde").props("type=date stack-label outlined dense").classes("grow")
                hasta = ui.input("Hasta").props("type=date stack-label outlined dense").classes("grow")
            cantidad = ui.label().classes("text-caption text-grey-7")

            ui.separator()
            ui.label("Leyenda").classes("text-subtitle1 text-weight-bold")
            for t in tipos:
                with ui.row().classes("items-center no-wrap gap-2"):
                    icono_tipo(t, 24)
                    ui.label(t["nombre"]).classes("text-body2")
            ui.label("Borde del pin = estado").classes("text-caption text-grey-7 q-mt-sm")
            with ui.row().classes("gap-1"):
                for id_estado, nombre in estados.items():
                    etiqueta(nombre, COLOR_ESTADO[id_estado])

    marcadores = []

    async def actualizar():
        """Lee los reportes con los filtros y vuelve a dibujar los pines."""
        reportes = await consultas.listar_reportes(cliente, {
            "desde": desde.value, "hasta": hasta.value, "id_tipo": tipo.value,
            "id_estado": estado.value, "gravedad": gravedad.value, "id_zona": zona.value})
        if estado.value is None:
            reportes = [r for r in reportes if r["id_estado"] != consultas.SOLUCIONADO]
        for capa in marcadores:
            mapa.remove_layer(capa)
        marcadores.clear()
        for r in reportes:
            marcadores.append(agregar_marcador(mapa, r))
        cantidad.text = f"{len(reportes)} reporte(s) con estos filtros"

    for filtro in (desde, hasta, tipo, estado, gravedad, zona):
        filtro.on_value_change(actualizar)

    # Ventana con el detalle al hacer clic en un pin.
    dialogo = ui.dialog()

    @ui.refreshable
    async def contenido(id_reporte):
        with ui.card().classes("q-pa-none gap-0").style("width: min(760px, 94vw)"):
            await tarjeta_reporte(cliente, perfil, id_reporte, lambda: contenido.refresh(id_reporte), compacta=True)

    async def abrir_reporte(e):
        dialogo.clear()
        with dialogo:
            await contenido(e.args)
        dialogo.open()

    ui.on("abrir_reporte", abrir_reporte)

    # Esperamos a que el mapa cargue en el navegador y dibujamos los distritos y los reportes.
    await mapa.initialized(timeout=15)
    for z in await consultas.zonas_con_poligono(cliente):
        if isinstance(z["geom"], dict):  # solo si llegó como GeoJSON.
            mapa.generic_layer(name="geoJSON", args=[z["geom"], {"color": "#2E7D32", "weight": 1, "fillOpacity": 0.03}])
    await actualizar()

    # Tiempo real.
    async def al_cambiar(cambios):
        avisar_cambios(cambios)
        await actualizar()
        # Si la ventana de un reporte está abierta, también se actualiza.
        if dialogo.value:
            contenido.refresh()

    await conexion.escuchar_cambios(cliente, al_cambiar)

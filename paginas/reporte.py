# Nuevo reporte (/reporte/nuevo), detalle del reporte (/reporte/{id}) y Mis reportes (/mis-reportes).

import base64

from nicegui import ui

import conexion
import consultas
import procesamiento
from conexion import ErrorBD
from paginas.login import encabezado, revisar_sesion
from paginas.mapa import (CENTRO, COLOR_GRAVEDAD, agregar_marcador, avisar_cambios, crear_mapa,
                          preparar_filas, tabla_reportes, tarjeta_reporte)

CRITERIOS = {"Bajo": "Área pequeña, sin riesgo inmediato para la salud.",
             "Medio": "Área mediana o molestia continua; afecta el paso o la convivencia.",
             "Alto": "Riesgo para la salud o el agua; cerca de escuelas, mercados, centros de salud o ríos."}

ICONO_GRAVEDAD = {"Bajo": "check_circle", "Medio": "error", "Alto": "warning"}


@ui.page("/reporte/nuevo")
async def pagina_nuevo():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Registro de nuevo reporte", "/reporte/nuevo")

    tipos = await consultas.tipos(cliente)
    elegido = {"id_tipo": None, "gravedad": None}   # lo que el usuario va eligiendo.
    punto = {}   # latitud y longitud elegidas.
    fotos = []   # fotos ya difuminadas y ubicación de captura.

    with ui.card().classes("w-full q-pa-lg").style("max-width: 760px; margin: 0 auto"):
        ui.label("Nuevo reporte ambiental").classes("text-h5 text-weight-bold")

        # Tipo: un botón por tipo, con su ícono y color.
        ui.label("Tipo de contaminación").classes("text-weight-medium q-mt-sm")

        @ui.refreshable
        def botones_tipo():
            with ui.row().classes("w-full gap-2"):
                for t in tipos:
                    activo = elegido["id_tipo"] == t["id_tipo"]
                    ui.button(t["nombre"], icon=t["icono"], on_click=lambda t=t: elegir("id_tipo", t["id_tipo"])) \
                        .props("no-caps" + ("" if activo else " outline")) \
                        .style(f"{'background' if activo else 'color'}: {t['color']} !important")
            if elegido["id_tipo"] == 7:
                ui.label("Explique en la descripción de qué se trata.").classes("text-caption text-grey-7")

        botones_tipo()

        # Gravedad: tres botones de colores.
        ui.label("Nivel de gravedad").classes("text-weight-medium q-mt-sm")

        @ui.refreshable
        def botones_gravedad():
            with ui.row().classes("w-full no-wrap gap-2"):
                for nivel in consultas.GRAVEDADES:
                    activo = elegido["gravedad"] == nivel
                    ui.button(nivel, icon=ICONO_GRAVEDAD[nivel], on_click=lambda n=nivel: elegir("gravedad", n)) \
                        .props("no-caps" + ("" if activo else " outline")).classes("grow") \
                        .style(f"{'background' if activo else 'color'}: {COLOR_GRAVEDAD[nivel]} !important")
            if elegido["gravedad"]:
                ui.label(CRITERIOS[elegido["gravedad"]]).classes("text-caption text-grey-7")

        botones_gravedad()

        # Tamaño, frecuencia y horario.
        ui.label("Tamaño del área afectada").classes("text-weight-medium q-mt-sm")
        tamano = ui.toggle(consultas.TAMANOS).props("no-caps spread").classes("w-full")
        ui.label("Pequeño: menos de 1 m² · Mediano: hasta unos 10 m² · Grande: más de 10 m²") \
            .classes("text-caption text-grey-7")
        ui.label("¿Cada cuánto pasa?").classes("text-weight-medium q-mt-sm")
        frecuencia = ui.toggle(consultas.FRECUENCIAS).props("no-caps spread").classes("w-full")
        ui.label("¿A qué hora se nota más? (opcional)").classes("text-weight-medium q-mt-sm")
        horario = ui.toggle(consultas.HORARIOS, clearable=True).props("no-caps spread").classes("w-full")

        # Características: el usuario marca las que ve.
        catalogo = await consultas.caracteristicas(cliente)
        marcadas = set()   # id de las características marcadas.

        def marcar(id_caracteristica, si):
            if si:
                marcadas.add(id_caracteristica)
            else:
                marcadas.discard(id_caracteristica)

        def chips(lista):
            with ui.row().classes("w-full gap-1"):
                for c in lista:
                    ui.chip(c["nombre"], selectable=True, selected=c["id_caracteristica"] in marcadas,
                            on_selection_change=lambda e, c=c: marcar(c["id_caracteristica"], e.value)) \
                        .props("outline color=primary")

        # Los detalles cambian según el tipo elegido.
        @ui.refreshable
        def detalles_tipo():
            propias = [c for c in catalogo if c["id_tipo"] is not None and c["id_tipo"] == elegido["id_tipo"]]
            if propias:
                nombre = next(t["nombre"] for t in tipos if t["id_tipo"] == elegido["id_tipo"])
                ui.label(f"¿Qué se ve? ({nombre})").classes("text-weight-medium q-mt-sm")
                chips(propias)

        detalles_tipo()
        ui.label("¿Está cerca de...?").classes("text-weight-medium q-mt-sm")
        chips([c for c in catalogo if c["grupo"] == "Cerca de"])
        ui.label("¿Qué efectos se notan?").classes("text-weight-medium q-mt-sm")
        chips([c for c in catalogo if c["grupo"] == "Efectos"])

        def elegir(campo, valor):
            elegido[campo] = valor
            if campo == "id_tipo":
                # Quitamos los detalles marcados de otro tipo.
                for c in catalogo:
                    if c["id_tipo"] is not None and c["id_tipo"] != valor:
                        marcadas.discard(c["id_caracteristica"])
                detalles_tipo.refresh()
            botones_tipo.refresh()
            botones_gravedad.refresh()

        # Descripción.
        ui.label("Descripción").classes("text-weight-medium q-mt-sm")
        descripcion = ui.textarea(placeholder="Ej.: Acumulación de residuos en la vía pública cerca de la unidad educativa. "
                                              "No escriba nombres ni teléfonos de otras personas.") \
            .props("outlined counter maxlength=500 autogrow").classes("w-full")

        # Ubicación.
        with ui.row().classes("w-full items-center q-mt-sm"):
            ui.label("Ubicación").classes("text-weight-medium")
            ui.space()
            ui.button("Usar mi ubicación", icon="my_location", on_click=lambda: mi_ubicacion()).props("flat no-caps")
        ui.label("Haga clic en el mapa donde está el problema.").classes("text-caption text-grey-7")
        mapa = crear_mapa(CENTRO, 13, "w-full h-72 rounded-borders")
        texto_punto = ui.label("Ubicación: sin elegir").classes("text-caption")

        # Fotos.
        ui.label("Fotografía (evidencia)").classes("text-weight-medium q-mt-sm")
        ui.label("Antes de subirlas se difuminan rostros y placas.").classes("text-caption text-grey-7")
        with ui.row().classes("w-full items-start gap-2"):
            vista = ui.row().classes("gap-2")
            subida = ui.upload(multiple=True, auto_upload=True, on_upload=foto_subida) \
                    .props('accept="image/*" capture="environment" max-file-size=10485760 '
                           'label="Tomar o subir foto" flat bordered color=grey-7') \
                    .classes("w-56")

        boton = ui.button("Registrar reporte", icon="send").classes("w-full q-mt-md").props("size=lg")

    def poner_punto(lat, lng):
        punto["latitud"], punto["longitud"] = round(lat, 6), round(lng, 6)
        # La primera vez creamos el marcador; después solo lo movemos.
        if "marcador" not in punto:
            punto["marcador"] = mapa.marker(latlng=(punto["latitud"], punto["longitud"]))
        punto["marcador"].move(punto["latitud"], punto["longitud"])
        texto_punto.text = f"Ubicación: {punto['latitud']}, {punto['longitud']}"

    def clic_mapa(e):
        poner_punto(e.args["latlng"]["lat"], e.args["latlng"]["lng"])

    async def mi_ubicacion():
        # Le pedimos al navegador la ubicación del celular o la computadora.
        posicion = await ui.run_javascript("""
            new Promise(listo => navigator.geolocation.getCurrentPosition(
                p => listo([p.coords.latitude, p.coords.longitude]), () => listo(null)))""", timeout=20)
        if not posicion:
            ui.notify("No se pudo obtener su ubicación", type="warning")
            return
        poner_punto(*posicion)
        mapa.set_center((punto["latitud"], punto["longitud"]))
        mapa.set_zoom(17)

    async def foto_subida(e):
        # Difuminamos la foto antes de subirla y mostramos cómo quedó.
        try:
            original = e.content.read()
            if len(original) > 10 * 1024 * 1024:
                ui.notify("La foto supera el límite de 10 MB.", type="warning")
                return
            contenido, cantidad = procesamiento.preparar_foto(original)
        except Exception:
            ui.notify("El archivo no es una imagen válida", type="negative")
            return
        fotos.append({"contenido": contenido, "captura": None})
        with vista:
            ui.image("data:image/jpeg;base64," + base64.b64encode(contenido).decode()) \
                .classes("w-32 h-32 rounded-borders").props("fit=cover")

        captura = await ui.run_javascript("""
            new Promise(resolve => navigator.geolocation.getCurrentPosition(
                p => resolve({latitud: p.coords.latitude, longitud: p.coords.longitude,
                              precision: p.coords.accuracy}),
                () => resolve(null), {enableHighAccuracy: true, timeout: 10000}))
        """, timeout=15)
        fotos[-1]["captura"] = captura
        if not captura:
            ui.notify("No se obtuvo la ubicación de la captura; quedará sin verificación.", type="warning")
        if cantidad:
            ui.notify(f"Se difuminaron {cantidad} rostro(s) o placa(s)")

    async def guardar():
        try:
            # Guardamos el reporte; los triggers ponen el código, la zona y el estado.
            nuevo = await consultas.crear_reporte(cliente, {
                "id_tipo": elegido["id_tipo"], "gravedad": elegido["gravedad"], "descripcion": descripcion.value,
                "latitud": punto.get("latitud"), "longitud": punto.get("longitud"),
                "tamano": tamano.value, "frecuencia": frecuencia.value, "horario": horario.value}, sorted(marcadas))
            for foto in fotos:
                captura = foto["captura"] or {}
                await consultas.subir_foto(
                    cliente, nuevo["id_reporte"], foto["contenido"],
                    latitud=captura.get("latitud"), longitud=captura.get("longitud"),
                    precision=captura.get("precision"))
        except ErrorBD as e:
            ui.notify(str(e), type="negative")
            return
        except Exception as e:
            ui.notify(f"No se pudo guardar la evidencia: {e}", type="negative")
            return
        ui.notify(f"Reporte {nuevo['codigo']} guardado", type="positive")
        ui.navigate.to(f"/reporte/{nuevo['id_reporte']}")

    mapa.on("map-click", clic_mapa)
    boton.on_click(guardar)


# Editar y eliminar (U y D del CRUD)

async def abrir_editar(cliente, r, al_guardar):
    """Ventana con los datos del reporte para corregirlos. La ubicación no se cambia."""
    tipos = {t["id_tipo"]: t["nombre"] for t in await consultas.tipos(cliente)}
    catalogo = await consultas.caracteristicas(cliente)
    marcadas = [c["id_caracteristica"] for c in await consultas.caracteristicas_de(cliente, r["id_reporte"])]

    def opciones_caracteristicas(id_tipo):
        # Las generales y los detalles del tipo elegido.
        return {c["id_caracteristica"]: f"{c['grupo']}: {c['nombre']}" for c in catalogo
                if c["id_tipo"] is None or c["id_tipo"] == id_tipo}

    def cambio_tipo(e):
        # Al cambiar de tipo quitamos los detalles del tipo anterior.
        caracteristicas.set_options(opciones_caracteristicas(e.value),
                                    value=[c for c in caracteristicas.value if c in opciones_caracteristicas(e.value)])

    with ui.dialog() as dialogo, ui.card().style("width: min(560px, 94vw)"):
        ui.label(f"Editar {r['codigo']}").classes("text-h6")
        tipo = ui.select(tipos, value=r["id_tipo"], label="Tipo de contaminación", on_change=cambio_tipo) \
            .props("outlined dense").classes("w-full")
        ui.label("Nivel de gravedad").classes("text-weight-medium")
        gravedad = ui.toggle(consultas.GRAVEDADES, value=r["gravedad"]).props("no-caps spread").classes("w-full")
        ui.label("Tamaño del área").classes("text-weight-medium")
        tamano = ui.toggle(consultas.TAMANOS, value=r["tamano"]).props("no-caps spread").classes("w-full")
        ui.label("¿Cada cuánto pasa?").classes("text-weight-medium")
        frecuencia = ui.toggle(consultas.FRECUENCIAS, value=r["frecuencia"]).props("no-caps spread").classes("w-full")
        ui.label("¿A qué hora se nota más? (opcional)").classes("text-weight-medium")
        horario = ui.toggle(consultas.HORARIOS, value=r["horario"], clearable=True) \
            .props("no-caps spread").classes("w-full")
        caracteristicas = ui.select(opciones_caracteristicas(r["id_tipo"]), value=marcadas, multiple=True,
                                    label="Características").props("outlined dense use-chips").classes("w-full")
        descripcion = ui.textarea("Descripción", value=r["descripcion"]) \
            .props("outlined counter maxlength=500 autogrow").classes("w-full")

        async def guardar():
            try:
                await consultas.editar_reporte(cliente, r["id_reporte"], {
                    "id_tipo": tipo.value, "gravedad": gravedad.value, "descripcion": descripcion.value,
                    "tamano": tamano.value, "frecuencia": frecuencia.value, "horario": horario.value},
                    caracteristicas.value)
            except ErrorBD as e:
                ui.notify(str(e), type="negative")
                return
            dialogo.close()
            ui.notify("Reporte actualizado", type="positive")
            al_guardar()

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Guardar cambios", icon="save", on_click=guardar)
    dialogo.open()


def abrir_eliminar(cliente, r):
    """Pide confirmación y elimina el reporte."""
    async def eliminar():
        try:
            await consultas.eliminar_reporte(cliente, r["id_reporte"])
        except ErrorBD as e:
            ui.notify(str(e), type="negative")
            return
        dialogo.close()
        ui.notify(f"Reporte {r['codigo']} eliminado", type="positive")
        ui.navigate.to("/")

    with ui.dialog() as dialogo, ui.card():
        ui.label(f"¿Eliminar el reporte {r['codigo']}?").classes("text-h6")
        ui.label("También se borran sus votos, fotos e historial. No se puede deshacer.").classes("text-grey-8")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Eliminar", icon="delete", color="negative", on_click=eliminar)
    dialogo.open()


@ui.page("/reporte/{id_reporte}")
async def pagina_detalle(id_reporte: int):
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Detalle del reporte")

    # Esta parte se vuelve a dibujar cuando hay cambios (al votar, o por tiempo real)
    @ui.refreshable
    async def detalle():
        with ui.card().classes("w-full q-pa-none gap-0"):
            r = await tarjeta_reporte(cliente, perfil, id_reporte, refrescar)

        # Editar y eliminar: el autor mientras está en Reportado, o el moderador (la BD lo vuelve a revisar)
        if consultas.puede_editar(perfil, r):
            with ui.row().classes("w-full justify-end"):
                ui.button("Editar", icon="edit", on_click=lambda: abrir_editar(cliente, r, refrescar)).props("outline")
                ui.button("Eliminar", icon="delete", color="negative", on_click=lambda: abrir_eliminar(cliente, r)) \
                    .props("outline")

        # Solo el moderador cambia el estado (la función de la BD lo vuelve a revisar)
        if perfil["rol"] == "moderador" and not r["es_final"]:
            with ui.card().classes("w-full"):
                ui.label("Cambiar estado (moderador)").classes("text-h6")
                nuevo_estado = ui.select({3: "Prioritario", 4: "En atención", 5: "Solucionado"},
                                         label="Nuevo estado").props("outlined dense").classes("w-full")
                comentario = ui.input("Comentario (obligatorio para Solucionado)") \
                    .props("outlined dense").classes("w-full")

                async def cambiar():
                    try:
                        await consultas.cambiar_estado(cliente, id_reporte, nuevo_estado.value, comentario.value)
                        ui.notify("Estado actualizado", type="positive")
                    except ErrorBD as e:
                        ui.notify(str(e), type="negative")
                    refrescar()

                ui.button("Cambiar estado", on_click=cambiar)

        # Historial de seguimiento.
        with ui.card().classes("w-full"):
            ui.label("Historial").classes("text-h6")
            with ui.timeline(side="right").classes("w-full"):
                for paso in await consultas.historial(cliente, id_reporte):
                    anterior = f"{paso['anterior']['nombre']} → " if paso["anterior"] else ""
                    quien = paso["usuario"]["nombre_usuario"] if paso["usuario"] else "Sistema"
                    ui.timeline_entry(paso["comentario"] or "", title=f"{anterior}{paso['nuevo']['nombre']}",
                                      subtitle=f"{consultas.formato_fecha(paso['fecha'])} · {quien}",
                                      color="green-8" if paso["id_estado_nuevo"] == consultas.SOLUCIONADO else "primary")
        return r

    # Fotos: las del reporte y las de vecinos que avisaron que ya no está.
    @ui.refreshable
    async def fotos():
        for titulo, lista in [("Evidencia del reporte", await consultas.evidencias(cliente, id_reporte)),
                              ("Fotos de que ya no está", await consultas.evidencias(cliente, id_reporte, True))]:
            if lista:
                with ui.card().classes("w-full"):
                    ui.label(titulo).classes("text-subtitle1 text-weight-bold")
                    for evidencia in lista:
                        ui.image(evidencia["url"]).classes("w-full rounded-borders")
                        if perfil["rol"] == "moderador":
                            estado = evidencia["verificacion_ubicacion"]
                            texto = estado
                            if evidencia["distancia_metros"] is not None:
                                texto += f" · {float(evidencia['distancia_metros']):.1f} m del punto"
                            ui.label(texto).classes(
                                "text-negative" if estado == "Inconsistencia de ubicación"
                                else "text-positive" if estado == "Ubicación verificada"
                                else "text-grey-7")

    def refrescar():
        detalle.refresh()
        fotos.refresh()

    with ui.row().classes("w-full items-start gap-4 flex-wrap lg:flex-nowrap"):
        with ui.column().classes("grow").style("min-width: 300px"):
            r = await detalle()
        with ui.column().classes("w-full lg:w-96"):
            with ui.card().classes("w-full q-pa-none overflow-hidden"):
                mapa = crear_mapa((r["latitud"], r["longitud"]), 16, "w-full h-64")
            await fotos()

    await mapa.initialized(timeout=15)
    marcador = [agregar_marcador(mapa, r, clic=False)]

    # Tiempo real: si cambia este reporte lo vemos al instante.
    async def al_cambiar(cambios):
        if any(c["tipo"] == "DELETE" and c["viejo"].get("id_reporte") == id_reporte for c in cambios):
            ui.notify("Este reporte fue eliminado", type="warning")
            ui.navigate.to("/")
            return
        if any(c["nuevo"].get("id_reporte") == id_reporte for c in cambios):
            refrescar()
            # Redibujamos el marcador por si cambió el color del estado.
            mapa.remove_layer(marcador[0])
            marcador[0] = agregar_marcador(mapa, await consultas.ver_reporte(cliente, id_reporte), clic=False)
            ui.notify("Este reporte se actualizó", type="info")

    await conexion.escuchar_cambios(cliente, al_cambiar)


@ui.page("/mis-reportes")
async def pagina_mis_reportes():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Mis reportes", "/mis-reportes")

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center"):
            ui.label("Reportes que registré").classes("text-h6")
            ui.space()
            ui.button("Nuevo reporte", icon="add", on_click=lambda: ui.navigate.to("/reporte/nuevo"))
        resumen = ui.label().classes("text-grey-7")
        tabla = tabla_reportes()

    async def actualizar():
        # El mismo listado de siempre, filtrado por el autor.
        reportes = await consultas.listar_reportes(cliente, {"id_usuario": perfil["id_usuario"]})
        tabla.rows = preparar_filas(reportes)
        solucionados = sum(r["id_estado"] == consultas.SOLUCIONADO for r in reportes)
        resumen.text = (f"{len(reportes)} reporte(s), {solucionados} solucionado(s)" if reportes
                        else "Todavía no registró reportes.")

    await actualizar()

    # Tiempo real: si alguien vota o el moderador cambia el estado, se ve aquí.
    async def al_cambiar(cambios):
        avisar_cambios(cambios)
        await actualizar()

    await conexion.escuchar_cambios(cliente, al_cambiar)

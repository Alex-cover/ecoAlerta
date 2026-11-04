# Estadísticas (/panel): consultas para encontrar problemas frecuentes, distritos y focos recurrentes.
# Usuarios (/usuarios): solo el moderador; ve a los usuarios y cambia su rol.

from datetime import datetime, timedelta

from nicegui import ui

import conexion
import consultas
from conexion import ErrorBD
from paginas.login import encabezado, revisar_sesion


def tabla(titulo, filas, columnas):
    """Tarjeta con un título y una tabla. columnas = [(campo, título), ...]"""
    with ui.card().classes("w-full"):
        ui.label(titulo).classes("text-h6")
        ui.table(columns=[{"name": c, "label": t, "field": c, "align": "left"} for c, t in columnas],
                 rows=filas, pagination=10).classes("w-full")


# Gráficos (ECharts, viene con NiceGUI)

# Colores de los gráficos: azul y naranja se distinguen bien también para daltónicos.
AZUL, NARANJA = "#4772df", "#49ad9f"
TEXTO_SUAVE, GRILLA = "#52514e", "#e6e5e1"


def grafico(titulo, opciones, alto=320):
    """Tarjeta con un título y un gráfico."""
    with ui.card().classes("grow").style("min-width: 320px; flex-basis: 420px"):
        ui.label(titulo).classes("text-h6")
        ui.echart(opciones).classes("w-full").style(f"height: {alto}px")


def ejes(categorias, horizontal=True):
    """Ejes suaves: grilla clara y textos en gris."""
    categoria = {"type": "category", "data": categorias, "inverse": horizontal,
                 "axisTick": {"show": False}, "axisLine": {"lineStyle": {"color": GRILLA}},
                 "axisLabel": {"color": TEXTO_SUAVE}}
    valor = {"type": "value", "minInterval": 1, "splitLine": {"lineStyle": {"color": GRILLA}},
             "axisLabel": {"color": TEXTO_SUAVE}}
    if horizontal:
        return {"yAxis": categoria, "xAxis": valor}
    return {"xAxis": categoria, "yAxis": valor}


def barras(nombres, valores, serie):
    """Barras horizontales de una sola serie (la más grande arriba)."""
    return {
        "grid": {"left": 8, "right": 24, "top": 8, "bottom": 8, "containLabel": True},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        **ejes(nombres),
        "series": [{"name": serie, "type": "bar", "data": valores, "barMaxWidth": 18,
                    "itemStyle": {"color": AZUL, "borderRadius": [0, 4, 4, 0]}}],
    }


def ultimas_semanas(filas, cantidad=12):
    """Las últimas semanas (lunes) con su total; las semanas sin reportes quedan en 0."""
    por_semana = {f["semana"]: f["total"] for f in filas}
    hoy = datetime.now(consultas.HORA_BOLIVIA).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    semanas = [lunes - timedelta(weeks=i) for i in range(cantidad - 1, -1, -1)]
    return [s.strftime("%d/%m") for s in semanas], [por_semana.get(s.isoformat(), 0) for s in semanas]


@ui.page("/panel")
async def pagina_panel():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Estadísticas", "/panel")
    filtros = {}
    with ui.card().classes("w-full"):
        ui.label("Filtrar estadísticas por fecha de creación").classes("text-subtitle1 text-weight-medium")
        with ui.row().classes("items-end gap-3"):
            desde = ui.input("Desde").props("type=date outlined dense")
            hasta = ui.input("Hasta").props("type=date outlined dense")
            def aplicar_filtro():
                filtros.clear()
                if desde.value:
                    filtros["desde"] = desde.value
                if hasta.value:
                    filtros["hasta"] = hasta.value
                contenido.refresh()
            def quitar_filtro():
                desde.value = None
                hasta.value = None
                filtros.clear()
                contenido.refresh()
            ui.button("Aplicar", icon="filter_alt", on_click=aplicar_filtro)
            ui.button("Limpiar", icon="clear", on_click=quitar_filtro).props("flat")

    # Se vuelve a dibujar cuando cambia un reporte (tiempo real)
    @ui.refreshable
    async def contenido():
        tipos = await consultas.resumen_tipo(cliente, filtros)
        zonas = await consultas.resumen_zona(cliente, filtros)
        focos = await consultas.focos_recurrentes(cliente)
        caracteristicas = await consultas.resumen_caracteristica(cliente, filtros)
        for c in caracteristicas:
            c["tipo"] = c["tipo"] or "Todos"

        # Totales.
        with ui.row().classes("w-full gap-4"):
            for icono, nombre, valor, color in [
                    ("description", "Reportes", sum(t["total"] for t in tipos), "#2563eb"),
                    ("warning", "Gravedad alta", sum(t["gravedad_alta"] for t in tipos), "#dc2626"),
                    ("check_circle", "Solucionados", sum(t["solucionados"] for t in tipos), "#16a34a"),
                    ("hub", "Focos recurrentes", len(focos), "#7c3aed")]:
                with ui.card().classes("grow q-pa-md").style("min-width: 160px"):
                    with ui.row().classes("items-center no-wrap"):
                        ui.icon(icono, size="32px").style(f"color:{color}")
                        with ui.column().classes("gap-0"):
                            ui.label(nombre).classes("text-grey-8")
                            ui.label(str(valor)).classes("text-h5 text-weight-bold")

        # Reportes nuevos por semana (línea)
        semanas, totales = ultimas_semanas(await consultas.reportes_por_semana(cliente, filtros))
        with ui.row().classes("w-full gap-4"):
            grafico("Reportes nuevos por semana (últimas 12)", {
                "grid": {"left": 8, "right": 24, "top": 16, "bottom": 8, "containLabel": True},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "line"}},
                **ejes(semanas, horizontal=False),
                "series": [{"name": "Reportes", "type": "line", "data": totales, "symbolSize": 8,
                            "lineStyle": {"width": 2, "color": AZUL}, "itemStyle": {"color": AZUL}}],
            }, alto=260)

        with ui.row().classes("w-full gap-4"):
            # Problemas más frecuentes (barras)
            con_datos = [t for t in tipos if t["total"] > 0]
            con_datos.sort(key=lambda t: t["total"], reverse=True)
            grafico("Problemas más frecuentes (por tipo)",
                    barras([t["tipo"] for t in con_datos], [t["total"] for t in con_datos], "Reportes"))

            # Distritos: sin solucionar y solucionados (barras apiladas)
            distritos = [z for z in zonas if z["total"] > 0]
            distritos.sort(key=lambda z: z["total"], reverse=True)
            grafico("Distritos con más reportes", {
                "grid": {"left": 8, "right": 24, "top": 32, "bottom": 8, "containLabel": True},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "legend": {"top": 0, "left": 0, "icon": "roundRect", "textStyle": {"color": TEXTO_SUAVE}},
                **ejes([z["zona"] for z in distritos]),
                "series": [
                    # El borde blanco deja una separación de 2 px entre las dos partes de la barra.
                    {"name": "Sin solucionar", "type": "bar", "stack": "total", "barMaxWidth": 18,
                     "data": [z["total"] - z["solucionados"] for z in distritos],
                     "itemStyle": {"color": AZUL, "borderColor": "#ffffff", "borderWidth": 1}},
                    {"name": "Solucionados", "type": "bar", "stack": "total", "barMaxWidth": 18,
                     "data": [z["solucionados"] for z in distritos],
                     "itemStyle": {"color": NARANJA, "borderColor": "#ffffff", "borderWidth": 1,
                                   "borderRadius": [0, 4, 4, 0]}},
                ],
            }, alto=max(320, 32 * len(distritos)))

        # Características más frecuentes (las 10 primeras)
        primeras = caracteristicas[:10]
        with ui.row().classes("w-full gap-4"):
            grafico("Características más frecuentes (10 primeras)",
                    barras([f"{c['grupo']}: {c['caracteristica']}" for c in primeras],
                           [c["total"] for c in primeras], "Reportes"), alto=max(280, 30 * len(primeras)))

        # Focos recurrentes: es una lista de lugares, mejor en tabla.
        tabla("Focos recurrentes (histórico; no depende del filtro de fechas)", focos,
              [("tipo", "Tipo"), ("zona", "Distrito"), ("total_reportes", "Reportes"), ("codigos", "Códigos")])

        # Los mismos datos de los gráficos, en tablas (para leer los números exactos)
        with ui.expansion("Ver los datos en tablas", icon="table_chart").classes("w-full"):
            tabla("Problemas más frecuentes (por tipo)", tipos,
                  [("tipo", "Tipo"), ("total", "Reportes"), ("gravedad_alta", "Gravedad alta"),
                   ("solucionados", "Solucionados")])
            tabla("Distritos con más reportes", zonas,
                  [("zona", "Distrito"), ("total", "Total"), ("reportados", "Reportados"),
                   ("confirmados", "Confirmados"), ("prioritarios", "Prioritarios"),
                   ("en_atencion", "En atención"), ("solucionados", "Solucionados")])
            tabla("Características más frecuentes", caracteristicas,
                  [("grupo", "Grupo"), ("caracteristica", "Característica"), ("tipo", "Tipo"),
                   ("total", "Reportes"), ("gravedad_alta", "Gravedad alta"), ("sin_solucionar", "Sin solucionar")])

    await contenido()

    async def al_cambiar(cambios):
        if any(c["tabla"] == "reporte" for c in cambios):
            contenido.refresh()

    await conexion.escuchar_cambios(cliente, al_cambiar)


@ui.page("/usuarios")
async def pagina_usuarios():
    cliente, perfil = await revisar_sesion()
    if not cliente:
        return
    encabezado(perfil, "Usuarios", "/usuarios")
    if perfil["rol"] != "moderador":
        ui.label("Solo los moderadores pueden ver esta página.").classes("text-h6 text-grey-7")
        return

    @ui.refreshable
    async def lista():
        filas = await consultas.usuarios(cliente)
        for f in filas:
            f["registro"] = consultas.formato_fecha(f["fecha_registro"])
            f["es_yo"] = f["id_usuario"] == perfil["id_usuario"]
        columnas = [{"name": c, "label": t, "field": c, "align": "left", "sortable": True} for c, t in
                    [("nombre_usuario", "Usuario"), ("nombre_completo", "Nombre"), ("rol", "Rol"),
                     ("reportes", "Reportes"), ("registro", "Registro"), ("accion", "")]]
        with ui.card().classes("w-full"):
            ui.label(f"{len(filas)} usuario(s) · {sum(f['rol'] == 'moderador' for f in filas)} moderador(es)") \
                .classes("text-grey-7")
            tabla = ui.table(columns=columnas, rows=filas, row_key="id_usuario", pagination=15).classes("w-full")
            tabla.add_slot("body-cell-rol", """<q-td :props="props">
                <q-badge rounded :color="props.value == 'moderador' ? 'indigo' : 'grey-7'" :label="props.value"
                         style="padding: 4px 10px"/></q-td>""")
            # El botón manda un evento a Python con la fila elegida.
            tabla.add_slot("body-cell-accion", """<q-td :props="props">
                <q-btn v-if="!props.row.es_yo" flat dense no-caps color="primary"
                       :label="props.row.rol == 'moderador' ? 'Quitar moderador' : 'Hacer moderador'"
                       @click="$parent.$emit('cambiar', props.row)"/>
                <q-btn v-if="!props.row.es_yo && props.row.rol == 'ciudadano'" flat dense no-caps
                       color="negative" label="Eliminar"
                       @click="$parent.$emit('eliminar', props.row)"/>
                <span v-if="props.row.es_yo" class="text-grey-6">(usted)</span></q-td>""")
            tabla.on("cambiar", cambiar)
            tabla.on("eliminar", eliminar)

    async def cambiar(e):
        nuevo = "ciudadano" if e.args["rol"] == "moderador" else "moderador"
        try:
            # La función de la BD vuelve a revisar que quien lo pide sea moderador.
            await consultas.cambiar_rol(cliente, e.args["id_usuario"], nuevo)
            ui.notify(f"{e.args['nombre_usuario']} ahora es {nuevo}", type="positive")
        except ErrorBD as error:
            ui.notify(str(error), type="negative")
        lista.refresh()

    async def eliminar(e):
        usuario = e.args
        with ui.dialog() as dialog, ui.card():
            ui.label(f"¿Eliminar a {usuario['nombre_usuario']}?").classes("text-h6")
            ui.label("También se borrarán sus reportes, votos y fotos. Esta acción no se puede deshacer.")
            with ui.row().classes("justify-end"):
                ui.button("Cancelar", on_click=dialog.close)

                async def confirmar():
                    try:
                        await consultas.eliminar_usuario(cliente, usuario["id_usuario"])
                        ui.notify(f"{usuario['nombre_usuario']} fue eliminado", type="positive")
                        dialog.close()
                        lista.refresh()
                    except ErrorBD as error:
                        ui.notify(str(error), type="negative")

                ui.button("Eliminar", color="negative", on_click=confirmar)
        dialog.open()

    ui.label("El moderador cambia roles y puede eliminar cuentas de vecinos. Usted no puede cambiar su propio rol.") \
        .classes("text-caption text-grey-7")
    await lista()

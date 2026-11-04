# Login, registro y el marco (menú lateral y barra de arriba) que usan todas las páginas.

from nicegui import ui

import conexion

VERDE = "#49ad9f"
AZUL_MENU = "#ffffff"
AZUL_ACTIVO = "#eef5fb"
TEXTO = "#172033"

# (ícono, texto, ruta, solo moderador)
MENU = [("home", "Inicio", "/", False),
        ("map", "Mapa", "/mapa", False),
        ("add_location_alt", "Nuevo reporte", "/reporte/nuevo", False),
        ("assignment", "Mis reportes", "/mis-reportes", False),
        ("bar_chart", "Estadísticas", "/panel", False),
        ("group", "Usuarios", "/usuarios", True)]


async def revisar_sesion():
    """Devuelve (cliente, perfil). Si no hay sesión, manda al login."""
    cliente = await conexion.obtener_cliente()
    perfil = conexion.usuario_actual()
    if not cliente or not perfil:
        ui.navigate.to("/login")
        return None, None
    return cliente, perfil


def logo(tamano="md"):
    """Muestra el logo ambiental."""
    ui.image("/static/logo.svg").style(
        f"width:{'96px' if tamano == 'lg' else '42px'}; "
        f"height:{'96px' if tamano == 'lg' else '42px'}")


def encabezado(perfil, titulo="", ruta="/"):
    """Menú lateral oscuro y barra de arriba con el título y el usuario."""
    ui.colors(primary=VERDE)
    ui.query("body").style("background:#f7f9fc; color:#172033")
    ui.add_head_html("""
        <style>
            .q-card { border: 1px solid #e8edf3; border-radius: 12px; box-shadow: 0 2px 8px rgba(23,32,51,.04); }
            .q-btn { border-radius: 8px; }
            .q-field--outlined .q-field__control { border-radius: 8px; }
        </style>
    """)

    async def salir():
        await conexion.cerrar_sesion()
        ui.navigate.to("/login")

    # Menú lateral.
    with ui.left_drawer(value=True).props("width=245 bordered").style(f"background:{AZUL_MENU}; border-color:#edf0f5") as menu:
        with ui.row().classes("items-center q-pa-md no-wrap"):
            logo()
            with ui.column().classes("gap-0"):
                ui.label("Voz Ambiental").style(f"color:{TEXTO}; font-weight:700")
                ui.label("El Alto").style("color:#7b8494; font-size:12px")
        for icono, texto, destino, solo_moderador in MENU:
            if solo_moderador and perfil["rol"] != "moderador":
                continue
            # La opción de la página actual se ve resaltada.
            activo = destino == ruta
            with ui.link(target=destino).classes("no-underline w-full"):
                with ui.row().classes("items-center q-px-md q-py-sm rounded-borders no-wrap q-mx-sm") \
                        .style(f"background:{AZUL_ACTIVO if activo else 'transparent'}"):
                    ui.icon(icono, color=VERDE if activo else "#657083")
                    ui.label(texto).style(f"color:{TEXTO if activo else '#4c5668'}")
        ui.space()
        with ui.row().classes("items-center q-px-md q-py-sm q-mx-sm cursor-pointer no-wrap").on("click", salir):
            ui.icon("logout", color="#657083")
            ui.label("Cerrar sesión").style("color:#4c5668")

    # Barra de arriba.
    with ui.header().classes("items-center bg-white text-grey-9 shadow-1 q-py-sm"):
        ui.button(icon="menu", on_click=menu.toggle).props("flat round color=grey-8")
        ui.label(titulo).style(f"color:{TEXTO}; font-size:20px; font-weight:700")
        ui.space()
        ui.icon("account_circle", size="sm", color="grey-7")
        with ui.column().classes("gap-0"):
            ui.label(perfil["nombre_usuario"]).classes("text-weight-medium")
            ui.label(perfil["rol"].capitalize()).classes("text-caption text-grey-7")


@ui.page("/login")
def pagina_login():
    ui.colors(primary=VERDE)
    ui.query("body").style("background:#f7f9fc")

    with ui.card().classes("absolute-center q-pa-lg items-center").style(
            "width: min(400px, 92vw); border:1px solid #e8edf3; border-radius:16px; "
            "box-shadow:0 10px 30px rgba(23,32,51,.08)"):
        logo("lg")
        ui.label("Voz Ambiental").classes("text-h6 text-weight-bold q-mt-sm")
        ui.label("Reporta y cuida El Alto").classes("text-grey-7 q-mb-md")

        # Ingresar.
        with ui.column().classes("w-full") as caja_ingresar:
            correo = ui.input("Correo").props("outlined dense").classes("w-full")
            with correo.add_slot("prepend"):
                ui.icon("mail")
            contrasena = ui.input("Contraseña", password=True, password_toggle_button=True) \
                .props("outlined dense").classes("w-full")
            with contrasena.add_slot("prepend"):
                ui.icon("lock")

            async def entrar():
                try:
                    cliente, sesion, perfil = await conexion.iniciar_sesion(correo.value, contrasena.value)
                except conexion.ErrorBD as e:
                    ui.notify(str(e), type="negative")
                    return
                conexion.guardar_sesion(cliente, sesion, perfil)
                ui.navigate.to("/")

            contrasena.on("keydown.enter", entrar)
            ui.button("Iniciar sesión", on_click=entrar).classes("w-full")
            with ui.row().classes("w-full justify-center items-center gap-1"):
                ui.label("¿No tienes cuenta?").classes("text-grey-7")
                ui.label("Regístrate").classes("text-primary text-weight-medium cursor-pointer") \
                    .on("click", lambda: cambiar(True))

        # Registrarse.
        with ui.column().classes("w-full") as caja_registro:
            r_correo = ui.input("Correo").props("outlined dense").classes("w-full")
            r_usuario = ui.input("Nombre de usuario (3 a 30 letras)").props("outlined dense").classes("w-full")
            r_nombre = ui.input("Nombre completo").props("outlined dense").classes("w-full")
            r_contrasena = ui.input("Contraseña (mínimo 6)", password=True, password_toggle_button=True) \
                .props("outlined dense").classes("w-full")
            acepta = ui.checkbox("Acepto usar el sistema con responsabilidad: no escribir datos "
                                 "personales de otras personas ni subir fotos sin su permiso.").classes("text-caption")

            async def crear_cuenta():
                if not acepta.value:
                    ui.notify("Debe aceptar el aviso de uso responsable", type="warning")
                    return
                try:
                    cliente, sesion, perfil = await conexion.registrar(
                        r_correo.value, r_contrasena.value, r_usuario.value.strip(), r_nombre.value.strip())
                except conexion.ErrorBD as e:
                    ui.notify(str(e), type="negative", multi_line=True)
                    return
                # Sin verificación de correo: entra directo.
                conexion.guardar_sesion(cliente, sesion, perfil)
                ui.navigate.to("/")

            ui.button("Crear cuenta", on_click=crear_cuenta).classes("w-full")
            with ui.row().classes("w-full justify-center items-center gap-1"):
                ui.label("¿Ya tienes cuenta?").classes("text-grey-7")
                ui.label("Inicia sesión").classes("text-primary text-weight-medium cursor-pointer") \
                    .on("click", lambda: cambiar(False))

    def cambiar(registro):
        caja_ingresar.set_visibility(not registro)
        caja_registro.set_visibility(registro)

    cambiar(False)

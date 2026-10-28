# Login, registro y el marco (menú lateral y barra de arriba) que usan todas las páginas.

from nicegui import ui

import conexion

VERDE = "#1f8f4e"
AZUL_MENU = "#14324a"

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
    """Círculo verde con una hoja."""
    with ui.element("div").classes("rounded-full flex items-center justify-center") \
            .style(f"background:{VERDE}; width:{'64px' if tamano == 'lg' else '40px'}; "
                   f"height:{'64px' if tamano == 'lg' else '40px'}"):
        ui.icon("eco", color="white", size="36px" if tamano == "lg" else "24px")


def encabezado(perfil, titulo="", ruta="/"):
    """Menú lateral oscuro y barra de arriba con el título y el usuario."""
    ui.colors(primary=VERDE)
    ui.query("body").style("background:#f3f6f8")

    async def salir():
        await conexion.cerrar_sesion()
        ui.navigate.to("/login")

    # Menú lateral.
    with ui.left_drawer(value=True).props("width=230 bordered").style(f"background:{AZUL_MENU}") as menu:
        with ui.row().classes("items-center q-pa-md no-wrap"):
            logo()
            with ui.column().classes("gap-0"):
                ui.label("Monitoreo Ambiental").classes("text-white text-weight-bold")
                ui.label("El Alto").classes("text-grey-5 text-caption")
        for icono, texto, destino, solo_moderador in MENU:
            if solo_moderador and perfil["rol"] != "moderador":
                continue
            # La opción de la página actual se ve resaltada.
            activo = destino == ruta
            with ui.link(target=destino).classes("no-underline w-full"):
                with ui.row().classes("items-center q-px-md q-py-sm rounded-borders no-wrap q-mx-sm") \
                        .style(f"background:{'#2563eb' if activo else 'transparent'}"):
                    ui.icon(icono, color="white")
                    ui.label(texto).classes("text-white")
        ui.space()
        with ui.row().classes("items-center q-px-md q-py-sm q-mx-sm cursor-pointer no-wrap").on("click", salir):
            ui.icon("logout", color="white")
            ui.label("Cerrar sesión").classes("text-white")

    # Barra de arriba.
    with ui.header().classes("items-center bg-white text-grey-9 shadow-1 q-py-sm"):
        ui.button(icon="menu", on_click=menu.toggle).props("flat round color=grey-8")
        ui.label(titulo).classes("text-h6")
        ui.space()
        ui.icon("account_circle", size="sm", color="grey-7")
        with ui.column().classes("gap-0"):
            ui.label(perfil["nombre_usuario"]).classes("text-weight-medium")
            ui.label(perfil["rol"].capitalize()).classes("text-caption text-grey-7")


@ui.page("/login")
def pagina_login():
    ui.colors(primary=VERDE)
    # Fondo con degradado (azul de la noche alteña al verde)
    ui.query("body").style(f"background: linear-gradient(135deg, {AZUL_MENU} 0%, #1d5a6b 55%, {VERDE} 100%)")

    with ui.card().classes("absolute-center q-pa-lg items-center").style("width: min(400px, 92vw)"):
        logo("lg")
        ui.label("Monitoreo Ambiental").classes("text-h6 text-weight-bold q-mt-sm")
        ui.label("El Alto").classes("text-grey-7 q-mb-md")

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

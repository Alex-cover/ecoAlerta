# Arranca la aplicacion

from nicegui import app, ui

import config
from paginas import login, mapa, panel, reporte

app.add_static_files("/static", "paginas")
ui.run(title="Voz Ambiental", port=8080, language="es", storage_secret=config.CLAVE_SESION)

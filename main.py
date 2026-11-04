# Arranca la aplicacion

import os

from nicegui import app, ui

import config
from paginas import login, mapa, panel, reporte

app.add_static_files("/static", "paginas")
ui.run(title="Voz Ambiental", port=int(os.environ.get("PORT", 8080)),
       host="0.0.0.0", language="es", storage_secret=config.CLAVE_SESION)

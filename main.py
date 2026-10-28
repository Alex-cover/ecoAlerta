# Arranca la aplicacion

import os

from nicegui import ui

import config
from paginas import login, mapa, panel, reporte

config.SUPABASE_URL = os.getenv("SUPABASE_URL", config.SUPABASE_URL)
config.SUPABASE_KEY = os.getenv("SUPABASE_KEY", config.SUPABASE_KEY)
config.CLAVE_SESION = os.getenv("CLAVE_SESION", config.CLAVE_SESION)

ui.run(title="EcoAlerta El Alto", host="0.0.0.0",
       port=int(os.getenv("PORT", "8080")), language="es", storage_secret=config.CLAVE_SESION)

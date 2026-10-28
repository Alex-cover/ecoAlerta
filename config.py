"""Configuración pública: los valores sensibles llegan por variables de entorno."""

import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
CLAVE_SESION = os.getenv("CLAVE_SESION", "")

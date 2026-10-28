# Copiar este archivo como config.py para ejecutar localmente.
# En un hosting se pueden usar estas mismas variables como Environment Variables.
import os

# config.py está en .gitignore para que las claves no se suban a GitHub.

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xxxx.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "clave-anon")  # la clave "anon", nunca service_role.
CLAVE_SESION = os.getenv("CLAVE_SESION", "cualquier-texto-largo")

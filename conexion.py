# Conexión a Supabase: clientes, login, registro y tiempo real.

# NiceGUI atiende a todos los navegadores en un solo programa. Por eso cada.
# navegador tiene SU PROPIO cliente de Supabase con su sesión: así la base de.
# datos sabe quién es cada usuario (auth.uid()) y aplica RLS.

import asyncio
import uuid

from nicegui import app, background_tasks, ui
from supabase import AsyncClientOptions, acreate_client

import config

# Clientes abiertos: clave = id del navegador.
clientes = {}


class ErrorBD(Exception):
    """Error con un mensaje en español para mostrar al usuario."""


def mensaje_error(e):
    """Convierte un error de Supabase en un mensaje entendible."""
    texto = str(getattr(e, "message", None) or e)
    if "uq_confirmacion_reporte_usuario" in texto:
        return ErrorBD("Usted ya votó en este reporte.")
    if "uq_usuario_nombre_usuario" in texto:
        return ErrorBD("Ese nombre de usuario ya está en uso.")
    if "ck_reporte_descripcion" in texto:
        return ErrorBD("La descripción debe tener entre 10 y 500 caracteres.")
    if "row-level security" in texto or "permission denied" in texto:
        return ErrorBD("No tiene permiso para realizar esta acción.")
    if "Invalid login credentials" in texto:
        return ErrorBD("Correo o contraseña incorrectos.")
    if "already registered" in texto:
        return ErrorBD("Ya existe una cuenta con ese correo.")
    if "rate limit" in texto:
        return ErrorBD("Supabase no deja enviar más correos. Desactive \"Confirm email\" en Authentication.")
    if "Email not confirmed" in texto:
        return ErrorBD("La cuenta no está verificada. Desactive \"Confirm email\" en Authentication.")
    # Los triggers y funciones ya mandan su mensaje en español.
    return ErrorBD(texto)


async def ejecutar(consulta):
    """Ejecuta una consulta de Supabase y devuelve los datos."""
    try:
        respuesta = await consulta.execute()
    except Exception as e:
        raise mensaje_error(e) from e
    return respuesta.data if respuesta else None


async def nuevo_cliente():
    # La sesión se guarda en memoria y el token se renueva solo.
    opciones = AsyncClientOptions(auto_refresh_token=True, persist_session=False)
    return await acreate_client(config.SUPABASE_URL, config.SUPABASE_KEY, options=opciones)


# Login y registro.

async def iniciar_sesion(correo, contrasena):
    """Inicia sesión. Devuelve (cliente, sesion, perfil)."""
    cliente = await nuevo_cliente()
    try:
        respuesta = await cliente.auth.sign_in_with_password({"email": correo.strip(), "password": contrasena})
    except Exception as e:
        raise mensaje_error(e) from e
    perfil = await ejecutar(cliente.table("usuario").select("*").eq("id_usuario", respuesta.user.id).single())
    return cliente, respuesta.session, perfil


async def registrar(correo, contrasena, nombre_usuario, nombre_completo):
    """Crea la cuenta y entra directo. Devuelve (cliente, sesion, perfil)."""
    cliente = await nuevo_cliente()
    try:
        respuesta = await cliente.auth.sign_up({
            "email": correo.strip(),
            "password": contrasena,
            "options": {"data": {"nombre_usuario": nombre_usuario, "nombre_completo": nombre_completo}},
        })
    except Exception as e:
        raise mensaje_error(e) from e
    # Sin verificación de correo, Supabase ya devuelve la sesión.
    if not respuesta.session:
        raise ErrorBD("Cuenta creada, pero Supabase pide verificar el correo. "
                      "Desactive \"Confirm email\" en Authentication → Sign In / Providers → Email.")
    # El trigger trg_usuario_nuevo ya creó el perfil con estos datos.
    perfil = await ejecutar(cliente.table("usuario").select("*").eq("id_usuario", respuesta.user.id).single())
    return cliente, respuesta.session, perfil


# Sesión del navegador.
# app.storage.user guarda datos del navegador aunque se recargue la página.

def guardar_sesion(cliente, sesion, perfil):
    clientes[app.storage.browser["id"]] = cliente
    app.storage.user["tokens"] = [sesion.access_token, sesion.refresh_token]
    app.storage.user["perfil"] = perfil


def usuario_actual():
    return app.storage.user.get("perfil")


def borrar_sesion():
    # Quitamos solo nuestras claves (clear() falla en Windows porque borra el archivo)
    app.storage.user.pop("tokens", None)
    app.storage.user.pop("perfil", None)


async def obtener_cliente():
    """Cliente con sesión del navegador actual (None si no inició sesión)."""
    clave = app.storage.browser["id"]
    if clave in clientes:
        return clientes[clave]

    # Si el servidor se reinició, armamos el cliente otra vez con los tokens guardados.
    tokens = app.storage.user.get("tokens")
    if not tokens:
        return None
    try:
        cliente = await nuevo_cliente()
        await cliente.auth.set_session(tokens[0], tokens[1])
    except Exception:
        # Tokens vencidos o de otra versión: hay que volver a iniciar sesión.
        borrar_sesion()
        return None
    clientes[clave] = cliente
    return cliente


async def cerrar_sesion():
    cliente = clientes.pop(app.storage.browser["id"], None)
    if cliente:
        # "local": solo cierra esta sesión, no la del mismo usuario en otro navegador.
        await cliente.auth.sign_out({"scope": "local"})
    borrar_sesion()


# Tiempo real.

async def escuchar_cambios(cliente, al_cambiar):
    """Suscribe la página actual a los cambios de reporte, confirmacion, seguimiento y evidencia.

    al_cambiar(cambios) es una función async que recibe la lista de cambios.
    Una confirmación genera varios cambios seguidos, así que los juntamos
    durante medio segundo y avisamos a la página una sola vez.
    """
    pagina = ui.context.client
    pendientes = []

    async def avisar():
        await asyncio.sleep(0.5)
        cambios = pendientes.copy()
        pendientes.clear()
        # "with pagina" para poder usar ui.notify en esa página.
        with pagina:
            await al_cambiar(cambios)

    def recibir(payload):
        datos = payload["data"]
        pendientes.append({"tabla": datos["table"], "tipo": datos["type"],
                           "nuevo": datos.get("record") or {}, "viejo": datos.get("old_record") or {}})
        if len(pendientes) == 1:
            background_tasks.create(avisar())

    # Realtime usa el token del usuario para respetar RLS.
    sesion = await cliente.auth.get_session()
    await cliente.realtime.set_auth(sesion.access_token)

    canal = cliente.channel(f"ecoalerta-{uuid.uuid4().hex[:8]}")
    for tabla in ("reporte", "confirmacion", "seguimiento", "evidencia"):
        canal.on_postgres_changes("*", schema="public", table=tabla, callback=recibir)
    await canal.subscribe()

    # Al cerrar la página dejamos de escuchar.
    async def cancelar():
        await cliente.remove_channel(canal)

    pagina.on_disconnect(cancelar)

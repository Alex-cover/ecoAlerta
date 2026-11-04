# Configuración de las pruebas. Ejecutar desde la carpeta del proyecto: pytest pruebas -v.
# Necesitan la cuenta admin@ecoalerta.test (la crea sql/09_datos_prueba.sql).
# Las demás cuentas de prueba (vecino1@ecoalerta.test, ...) se registran solas la primera vez.
# Los reportes que crean llevan "[PRUEBA]"; para dejar la base limpia otra vez,
# volver a ejecutar sql/09_datos_prueba.sql.

import sys
from pathlib import Path

import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar conexion y consultas.

import conexion  # noqa: E402
import consultas  # noqa: E402

LAT, LON = -16.5330, -68.1630  # un punto dentro del Distrito 1.
CONTRASENA = "Prueba123!"


async def entrar(nombre):
    """Inicia sesión con un usuario de prueba; si todavía no existe, lo registra."""
    correo = f"{nombre}@ecoalerta.test"
    try:
        cliente, _, _ = await conexion.iniciar_sesion(correo, CONTRASENA)
    except conexion.ErrorBD:
        cliente, _, _ = await conexion.registrar(correo, CONTRASENA, f"{nombre}_prueba", f"[PRUEBA] {nombre}")
    return cliente


async def crear_reporte(cliente, gravedad="Medio", lat=LAT, lon=LON, caracteristicas=()):
    return await consultas.crear_reporte(cliente, {
        "id_tipo": 1, "gravedad": gravedad, "descripcion": "[PRUEBA] Reporte creado por pytest.",
        "latitud": lat, "longitud": lon, "tamano": "Mediano", "frecuencia": "A veces"}, caracteristicas)


@pytest_asyncio.fixture
async def vecino1():
    return await entrar("vecino1")


@pytest_asyncio.fixture
async def moderador():
    cliente = await entrar("moderador")
    # La primera vez se registra como ciudadano: el admin lo vuelve moderador.
    perfil = await conexion.ejecutar(cliente.table("usuario").select("id_usuario, rol")
                                     .eq("id_usuario", await consultas.mi_id(cliente)).single())
    if perfil["rol"] != "moderador":
        await consultas.cambiar_rol(await entrar("admin"), perfil["id_usuario"], "moderador")
    return cliente

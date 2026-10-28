# Pruebas de concurrencia: varias operaciones al mismo tiempo sobre el mismo reporte.
# asyncio.gather manda todas las peticiones a la vez, cada usuario con su propio cliente.

import asyncio

import pytest

import consultas
from conftest import crear_reporte, entrar

pytestmark = pytest.mark.asyncio


async def test_varios_confirman_a_la_vez(vecino1):
    nuevo = await crear_reporte(vecino1, gravedad="Alto")
    clientes = [await entrar(n) for n in ("vecino2", "vecino3", "vecino4", "vecino5", "vecino6", "moderador")]

    await asyncio.gather(*[consultas.votar(c, nuevo["id_reporte"], True) for c in clientes])

    # No se perdió ninguna confirmación (el UPDATE +1 es atómico y votar() usa FOR UPDATE)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert detalle["total_confirmaciones"] == 6
    assert detalle["estado"] == "Prioritario"   # Alto con 5 o más.
    # Cada cambio automático quedó una sola vez en el historial.
    estados = [h["nuevo"]["nombre"] for h in await consultas.historial(vecino1, nuevo["id_reporte"])]
    assert estados == ["Reportado", "Confirmado", "Prioritario"]


async def test_mismo_usuario_confirma_dos_veces_a_la_vez(vecino1):
    nuevo = await crear_reporte(vecino1)
    pestana1 = await entrar("vecino2")
    pestana2 = await entrar("vecino2")

    resultados = await asyncio.gather(consultas.votar(pestana1, nuevo["id_reporte"], True),
                                      consultas.votar(pestana2, nuevo["id_reporte"], True),
                                      return_exceptions=True)

    # Una funciona; la otra espera (FOR UPDATE), ve el primer voto y falla con un mensaje claro.
    errores = [str(r) for r in resultados if isinstance(r, Exception)]
    assert errores == ['Usted ya votó "Sigue ahí" en este reporte']
    assert (await consultas.ver_reporte(vecino1, nuevo["id_reporte"]))["total_confirmaciones"] == 1


async def test_dos_moderadores_a_la_vez(vecino1, moderador):
    nuevo = await crear_reporte(vecino1)
    admin = await entrar("admin")  # también es moderador.

    resultados = await asyncio.gather(
        consultas.cambiar_estado(moderador, nuevo["id_reporte"], consultas.EN_ATENCION, "[PRUEBA] A"),
        consultas.cambiar_estado(admin, nuevo["id_reporte"], consultas.EN_ATENCION, "[PRUEBA] B"),
        return_exceptions=True)

    # Uno gana; el otro espera (FOR UPDATE), ve el estado nuevo y se rechaza.
    assert sum(isinstance(r, Exception) for r in resultados) == 1
    historial = await consultas.historial(vecino1, nuevo["id_reporte"])
    assert [h["nuevo"]["nombre"] for h in historial] == ["Reportado", "En atención"]


async def test_varios_dicen_ya_no_esta_a_la_vez(vecino1):
    nuevo = await crear_reporte(vecino1)
    clientes = [await entrar(n) for n in ("vecino2", "vecino3", "vecino4", "vecino5", "vecino6")]

    resultados = await asyncio.gather(*[consultas.votar(c, nuevo["id_reporte"], False) for c in clientes],
                                      return_exceptions=True)

    # Los 3 primeros cuentan y el reporte pasa a Solucionado; los otros 2 ya lo encuentran cerrado.
    assert sum(isinstance(r, Exception) for r in resultados) == 2
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert detalle["total_ya_no_esta"] == 3
    estados = [h["nuevo"]["nombre"] for h in await consultas.historial(vecino1, nuevo["id_reporte"])]
    assert estados == ["Reportado", "Solucionado"]

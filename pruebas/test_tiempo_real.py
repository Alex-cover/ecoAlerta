# Prueba de tiempo real: la sesión B escucha y la sesión A hace cambios (como en la defensa).

import asyncio

import pytest

import consultas
from conftest import crear_reporte, entrar

pytestmark = pytest.mark.asyncio


async def test_sesion_b_recibe_los_cambios(vecino1, moderador):
    # Sesión B: se suscribe a los cambios de reporte.
    sesion_b = await entrar("vecino2")
    recibidos = []
    token = (await sesion_b.auth.get_session()).access_token
    await sesion_b.realtime.set_auth(token)
    canal = sesion_b.channel("prueba")
    canal.on_postgres_changes("*", schema="public", table="reporte",
                              callback=lambda payload: recibidos.append(payload["data"]))
    await canal.subscribe()
    await asyncio.sleep(3)  # esperamos a que la suscripción quede activa.

    # Caso 1: A crea un reporte.
    nuevo = await crear_reporte(vecino1)
    # Caso 2: un vecino confirma y el moderador cambia el estado.
    await consultas.votar(await entrar("vecino3"), nuevo["id_reporte"], True)
    await consultas.cambiar_estado(moderador, nuevo["id_reporte"], consultas.EN_ATENCION, "[PRUEBA]")
    await asyncio.sleep(5)

    eventos = [(d["type"], d["record"]["id_estado"], d["record"]["total_confirmaciones"]) for d in recibidos
               if d["record"]["id_reporte"] == nuevo["id_reporte"]]
    assert ("INSERT", consultas.REPORTADO, 0) in eventos
    assert ("UPDATE", consultas.REPORTADO, 1) in eventos
    assert ("UPDATE", consultas.EN_ATENCION, 1) in eventos
    await sesion_b.remove_channel(canal)

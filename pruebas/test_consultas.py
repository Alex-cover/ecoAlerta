# Pruebas de las consultas de análisis (vistas). Funcionan con la base vacía o con datos.

import random

import pytest

import consultas
from conftest import crear_reporte

pytestmark = pytest.mark.asyncio


async def test_resumenes_cuadran_con_los_reportes(vecino1):
    total = len(await consultas.listar_reportes(vecino1))
    assert sum(t["total"] for t in await consultas.resumen_tipo(vecino1)) == total
    assert sum(z["total"] for z in await consultas.resumen_zona(vecino1)) == total


async def test_dbscan_necesita_tres_reportes(vecino1):
    # Un lugar al azar del Distrito 7 sin otros reportes de residuos cerca.
    # (al azar para que la prueba funcione aunque se ejecute varias veces)
    lat, lon = random.uniform(-16.468, -16.462), random.uniform(-68.268, -68.240)
    antes = len(await consultas.focos_recurrentes(vecino1))

    await crear_reporte(vecino1, lat=lat, lon=lon)
    await crear_reporte(vecino1, lat=lat + 0.0002, lon=lon)          # a unos 22 m.
    assert len(await consultas.focos_recurrentes(vecino1)) == antes  # 2 no forman foco.

    await crear_reporte(vecino1, lat=lat, lon=lon + 0.0003)          # a unos 32 m.
    assert len(await consultas.focos_recurrentes(vecino1)) == antes + 1

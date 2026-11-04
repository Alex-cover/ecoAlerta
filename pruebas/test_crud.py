# Pruebas de CRUD y de las reglas de la base de datos (triggers y RLS).

import io
import re

import pytest
from PIL import Image

import conexion
import consultas
from conexion import ErrorBD
from conftest import crear_reporte, entrar

pytestmark = pytest.mark.asyncio


async def test_login_correcto_e_incorrecto(vecino1):  # vecino1 asegura que la cuenta exista.
    _, _, perfil = await conexion.iniciar_sesion("vecino1@ecoalerta.test", "Prueba123!")
    assert perfil["nombre_usuario"] == "vecino1_prueba"
    with pytest.raises(ErrorBD, match="incorrectos"):
        await conexion.iniciar_sesion("vecino1@ecoalerta.test", "mala")


async def test_crear_reporte(vecino1):
    nuevo = await crear_reporte(vecino1)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    # Los triggers generan el código, asignan la zona y el estado inicial.
    assert re.fullmatch(r"REP-\d{4}-\d{6}", detalle["codigo"])
    assert detalle["zona"] == "Distrito 1"
    assert detalle["estado"] == "Reportado"
    # Y dejan la primera fila del historial.
    assert len(await consultas.historial(vecino1, nuevo["id_reporte"])) == 1


async def test_reporte_fuera_de_el_alto(vecino1):
    with pytest.raises(ErrorBD, match="no está dentro"):
        await crear_reporte(vecino1, lat=-16.40, lon=-68.00)


async def test_listar_con_filtros(vecino1):
    nuevo = await crear_reporte(vecino1, gravedad="Alto")
    reportes = await consultas.listar_reportes(vecino1, {"id_estado": consultas.REPORTADO, "gravedad": "Alto",
                                                         "id_usuario": await consultas.mi_id(vecino1)})
    assert nuevo["id_reporte"] in [r["id_reporte"] for r in reportes]
    assert all(r["estado"] == "Reportado" and r["gravedad"] == "Alto" for r in reportes)


async def test_reglas_de_votos(vecino1):
    nuevo = await crear_reporte(vecino1)
    vecino2 = await entrar("vecino2")
    await consultas.votar(vecino2, nuevo["id_reporte"], True)

    # No puede votar lo mismo dos veces ni confirmar su propio reporte.
    with pytest.raises(ErrorBD, match="ya votó"):
        await consultas.votar(vecino2, nuevo["id_reporte"], True)
    with pytest.raises(ErrorBD, match="propio reporte"):
        await consultas.votar(vecino1, nuevo["id_reporte"], True)

    # Pero el autor sí puede avisar que ya no está.
    await consultas.votar(vecino1, nuevo["id_reporte"], False)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert (detalle["total_confirmaciones"], detalle["total_ya_no_esta"]) == (1, 1)


async def test_cambiar_voto(vecino1):
    nuevo = await crear_reporte(vecino1)
    vecino2 = await entrar("vecino2")
    await consultas.votar(vecino2, nuevo["id_reporte"], True)
    # Tiempo después ve que ya limpiaron: cambia su voto (no se cuenta dos veces)
    await consultas.votar(vecino2, nuevo["id_reporte"], False)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert (detalle["total_confirmaciones"], detalle["total_ya_no_esta"]) == (0, 1)
    assert await consultas.mi_voto(vecino2, nuevo["id_reporte"]) is False


async def test_tres_confirmaciones_pasa_a_confirmado(vecino1):
    nuevo = await crear_reporte(vecino1)
    for nombre in ("vecino2", "vecino3", "vecino4"):
        await consultas.votar(await entrar(nombre), nuevo["id_reporte"], True)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert detalle["total_confirmaciones"] == 3
    assert detalle["estado"] == "Confirmado"


async def test_tres_ya_no_esta_pasa_a_solucionado(vecino1):
    nuevo = await crear_reporte(vecino1)
    for nombre in ("vecino2", "vecino3", "vecino4"):
        await consultas.votar(await entrar(nombre), nuevo["id_reporte"], False)
    detalle = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert detalle["estado"] == "Solucionado"
    # Queda en el historial como cambio automático (sin usuario)
    ultimo = (await consultas.historial(vecino1, nuevo["id_reporte"]))[-1]
    assert ultimo["usuario"] is None and "ya no está" in ultimo["comentario"]
    # Un reporte solucionado ya no recibe votos.
    with pytest.raises(ErrorBD, match="solucionado"):
        await consultas.votar(await entrar("vecino5"), nuevo["id_reporte"], True)


async def test_foto_de_ya_no_esta(vecino1):
    nuevo = await crear_reporte(vecino1)
    vecino2 = await entrar("vecino2")
    id_voto = await consultas.votar(vecino2, nuevo["id_reporte"], False)

    # Una foto pequeña de prueba.
    salida = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(salida, format="JPEG")
    await consultas.subir_foto(vecino2, nuevo["id_reporte"], salida.getvalue(), id_voto)
    assert len(await consultas.urls_fotos(vecino1, nuevo["id_reporte"], ya_no_esta=True)) == 1
    assert await consultas.urls_fotos(vecino1, nuevo["id_reporte"]) == []

    # Otro usuario no puede subir una foto a nombre de ese voto (RLS)
    with pytest.raises(ErrorBD, match="permiso"):
        await consultas.subir_foto(await entrar("vecino3"), nuevo["id_reporte"], salida.getvalue(), id_voto)


async def test_cambio_de_estado(vecino1, moderador):
    nuevo = await crear_reporte(vecino1)
    # Un ciudadano no puede cambiar el estado.
    with pytest.raises(ErrorBD, match="moderador"):
        await consultas.cambiar_estado(vecino1, nuevo["id_reporte"], consultas.EN_ATENCION)
    # El moderador sí, y queda en el historial con su nombre.
    await consultas.cambiar_estado(moderador, nuevo["id_reporte"], consultas.EN_ATENCION, "[PRUEBA]")
    historial = await consultas.historial(moderador, nuevo["id_reporte"])
    assert historial[-1]["nuevo"]["nombre"] == "En atención"
    assert historial[-1]["usuario"]["nombre_usuario"] == "moderador_prueba"
    # Solucionado exige comentario.
    with pytest.raises(ErrorBD, match="comentario"):
        await consultas.cambiar_estado(moderador, nuevo["id_reporte"], consultas.SOLUCIONADO, "")


async def test_nadie_edita_directo(vecino1):
    # Sin política de UPDATE, RLS no deja cambiar el estado a mano: solo con editar_reporte() o cambiar_estado()
    nuevo = await crear_reporte(vecino1)
    filas = await conexion.ejecutar(vecino1.table("reporte").update({"id_estado": consultas.SOLUCIONADO})
                                    .eq("id_reporte", nuevo["id_reporte"]))
    assert filas == []
    assert (await consultas.ver_reporte(vecino1, nuevo["id_reporte"]))["estado"] == "Reportado"


async def test_mis_reportes(vecino1):
    nuevo = await crear_reporte(vecino1)
    yo = await consultas.mi_id(vecino1)
    reportes = await consultas.listar_reportes(vecino1, {"id_usuario": yo})
    assert nuevo["id_reporte"] in [r["id_reporte"] for r in reportes]
    assert all(r["id_usuario"] == yo for r in reportes)


async def test_cambiar_rol(vecino1, moderador):
    await entrar("vecino6")  # por si la cuenta todavía no existe.
    vecino6 = next(u for u in await consultas.usuarios(moderador) if u["nombre_usuario"] == "vecino6_prueba")
    # Un ciudadano no puede cambiar roles.
    with pytest.raises(ErrorBD, match="moderador"):
        await consultas.cambiar_rol(vecino1, vecino6["id_usuario"], "moderador")
    # El moderador sí (y lo dejamos como estaba)
    await consultas.cambiar_rol(moderador, vecino6["id_usuario"], "moderador")
    await consultas.cambiar_rol(moderador, vecino6["id_usuario"], "ciudadano")
    # Nadie cambia su propio rol.
    yo = next(u for u in await consultas.usuarios(moderador) if u["nombre_usuario"] == "moderador_prueba")
    with pytest.raises(ErrorBD, match="propio rol"):
        await consultas.cambiar_rol(moderador, yo["id_usuario"], "ciudadano")


async def test_caracteristicas(vecino1):
    # 1 = Escuela o colegio (general), 20 = Basura doméstica (residuos sólidos); el reporte es de residuos.
    nuevo = await crear_reporte(vecino1, caracteristicas=[1, 20])
    nombres = [c["nombre"] for c in await consultas.caracteristicas_de(vecino1, nuevo["id_reporte"])]
    assert nombres == ["Escuela o colegio", "Basura doméstica"]

    # 31 = Llantas es de quema de basura: el trigger no deja marcarla en un reporte de residuos.
    with pytest.raises(ErrorBD, match="no corresponde"):
        await conexion.ejecutar(vecino1.table("reporte_caracteristica")
                                .insert({"id_reporte": nuevo["id_reporte"], "id_caracteristica": 31}))
    # Otro usuario no puede marcar características en un reporte ajeno (RLS)
    with pytest.raises(ErrorBD, match="permiso"):
        await conexion.ejecutar((await entrar("vecino2")).table("reporte_caracteristica")
                                .insert({"id_reporte": nuevo["id_reporte"], "id_caracteristica": 2}))


async def test_tamano_y_frecuencia_validos(vecino1):
    # El CHECK de la tabla solo acepta los valores de la lista.
    with pytest.raises(ErrorBD):
        await consultas.crear_reporte(vecino1, {
            "id_tipo": 1, "gravedad": "Bajo", "descripcion": "[PRUEBA] Tamaño inválido.",
            "latitud": -16.533, "longitud": -68.163, "tamano": "Enorme", "frecuencia": "A veces"})


# CRUD de reportes: editar (U) y eliminar (D)

DATOS_EDITADOS = {"id_tipo": 2, "gravedad": "Alto", "descripcion": "[PRUEBA] Reporte editado por pytest.",
                  "tamano": "Grande", "frecuencia": "Todos los días", "horario": "Noche"}


async def test_editar_reporte(vecino1, moderador):
    nuevo = await crear_reporte(vecino1, caracteristicas=[1, 20])
    # El autor lo edita mientras está en Reportado; se reemplazan las características (31 = Llantas, de quema)
    await consultas.editar_reporte(vecino1, nuevo["id_reporte"], DATOS_EDITADOS, [1, 31])
    r = await consultas.ver_reporte(vecino1, nuevo["id_reporte"])
    assert (r["tipo"], r["gravedad"], r["tamano"], r["horario"]) == ("Quema de basura", "Alto", "Grande", "Noche")
    assert r["codigo"] == nuevo["codigo"]   # el código no cambia.
    nombres = [c["nombre"] for c in await consultas.caracteristicas_de(vecino1, nuevo["id_reporte"])]
    assert nombres == ["Escuela o colegio", "Llantas"]

    # Otro vecino no puede editarlo.
    with pytest.raises(ErrorBD, match="autor o un moderador"):
        await consultas.editar_reporte(await entrar("vecino2"), nuevo["id_reporte"], DATOS_EDITADOS)

    # Cuando ya lo confirmaron, el autor no puede editarlo, pero el moderador sí.
    for nombre in ("vecino2", "vecino3", "vecino4"):
        await consultas.votar(await entrar(nombre), nuevo["id_reporte"], True)
    with pytest.raises(ErrorBD, match="Reportado"):
        await consultas.editar_reporte(vecino1, nuevo["id_reporte"], DATOS_EDITADOS)
    await consultas.editar_reporte(moderador, nuevo["id_reporte"], {**DATOS_EDITADOS, "gravedad": "Medio"})
    assert (await consultas.ver_reporte(vecino1, nuevo["id_reporte"]))["gravedad"] == "Medio"


async def test_eliminar_reporte(vecino1, moderador):
    # Otro vecino no puede eliminarlo (RLS); el autor sí, mientras está en Reportado.
    nuevo = await crear_reporte(vecino1)
    with pytest.raises(ErrorBD, match="eliminar"):
        await consultas.eliminar_reporte(await entrar("vecino2"), nuevo["id_reporte"])
    await consultas.eliminar_reporte(vecino1, nuevo["id_reporte"])
    assert nuevo["id_reporte"] not in [r["id_reporte"] for r in await consultas.listar_reportes(vecino1)]

    # Ya confirmado: el autor no puede eliminarlo, el moderador sí (se borran también votos e historial)
    otro = await crear_reporte(vecino1)
    for nombre in ("vecino2", "vecino3", "vecino4"):
        await consultas.votar(await entrar(nombre), otro["id_reporte"], True)
    with pytest.raises(ErrorBD, match="eliminar"):
        await consultas.eliminar_reporte(vecino1, otro["id_reporte"])
    await consultas.eliminar_reporte(moderador, otro["id_reporte"])
    assert await consultas.historial(moderador, otro["id_reporte"]) == []

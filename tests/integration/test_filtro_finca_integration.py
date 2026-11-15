# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-25/35/75/77: fincas e infraestructuras del usuario y filtro por finca combinado con su alcance |
"""Filtro por finca de Suministros, Finanzas e Integración contable.

El usuario solo filtra entre sus fincas (el Administrador entre todas) y el filtro se combina con su
alcance: pedir una finca ajena devuelve una lista vacía, nunca los datos de otro.
"""
from __future__ import annotations

import random

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.infrastructure.adapters.alcance_activo_m02_adapter import AlcanceActivoM02Adapter

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _router_activos(integration_app):
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router

    if not any(getattr(r, "path", "") == "/activos-biologicos" for r in integration_app.routes):
        integration_app.include_router(router)


def _id() -> int:
    return random.randint(10_000_000, 2_000_000_000)


def _finca(db: Session, id_usuario: int | None, nombre: str) -> int:
    id_finca = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("""INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion,
                         es_activo, tipo_id_tributaria, numero_id_tributaria, dv, razon_social)
                       VALUES (:f, :n, '{}', 10, now(), now(), true, 'NIT', '900123456', '8', 'Ganadería de Prueba SAS')"""),
               {"f": id_finca, "n": nombre})
    if id_usuario is not None:
        db.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
                   {"u": id_usuario, "f": id_finca})
    db.execute(text("""INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, superficie, es_activo, tipo)
                       VALUES (:f, :n, :f, 100, true, 'Corral')"""), {"f": id_finca, "n": f"Corral {id_finca}"})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_finca


def _activo(db: Session, id_finca: int, id_usuario: int) -> int:
    id_activo = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("""INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura,
                         tipo, fecha_inicio_ciclo, id_estado, descripcion, origen_financiero, costo_adquisicion,
                         atributos_dinamicos, id_usuario, fecha_creacion, soporte_documental, detalles_procedencia)
                       VALUES (:a, 1, :ident, :i, 'INDIVIDUAL', current_date, 1, 'Filtro finca', 'compra', 1000, '{}', :u,
                               now(), 'Factura 1', '')"""),
               {"a": id_activo, "ident": f"FF-{id_activo}", "i": id_finca, "u": id_usuario})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_activo


def test_mis_fincas_sin_permiso_de_configuracion_y_global_para_el_administrador(
        client, db_session, crear_usuario_db, crear_auth_headers):
    contador = crear_usuario_db(id_rol=5)  # sin «fincas · Leer»: antes recibía 403 en el filtro
    admin = crear_usuario_db(id_rol=1)
    propia = _finca(db_session, contador["id_usuario"], "Finca Propia Filtro")
    ajena = _finca(db_session, None, "Finca Ajena Filtro")

    headers = crear_auth_headers(contador)
    r = client.get("/usuarios/me/fincas", headers=headers)
    assert r.status_code == 200, r.text
    ids = {f["id_finca"] for f in r.json()["items"]}
    assert propia in ids and ajena not in ids
    [fila] = [f for f in r.json()["items"] if f["id_finca"] == propia]
    assert (fila["nombre"], fila["numero_id_tributaria"]) == ("Finca Propia Filtro", "900123456")

    # Áreas de una finca propia sin el permiso «infraestructuras»; de una ajena, ninguna.
    areas = client.get(f"/usuarios/me/fincas/{propia}/infraestructuras", headers=headers)
    assert areas.status_code == 200, areas.text
    assert areas.json()["items"] == [{"id_infraestructura": propia, "nombre": f"Corral {propia}"}]
    assert client.get(f"/usuarios/me/fincas/{ajena}/infraestructuras", headers=headers).json()["items"] == []

    ids_admin = {f["id_finca"] for f in client.get("/usuarios/me/fincas", headers=crear_auth_headers(admin)).json()["items"]}
    assert {propia, ajena} <= ids_admin


def test_el_filtro_por_finca_se_combina_con_el_alcance(db_session, crear_usuario_db):
    contador = crear_usuario_db(id_rol=5)
    propia = _finca(db_session, contador["id_usuario"], "Finca Propia Alcance")
    otra_propia = _finca(db_session, contador["id_usuario"], "Finca Propia Dos")
    ajena = _finca(db_session, None, "Finca Ajena Alcance")
    en_propia = _activo(db_session, propia, contador["id_usuario"])
    en_otra = _activo(db_session, otra_propia, contador["id_usuario"])
    en_ajena = _activo(db_session, ajena, contador["id_usuario"])
    alcance = AlcanceActivoM02Adapter(db_session)

    assert {en_propia, en_otra} <= set(alcance.listar_ids_activos_permitidos(contador["id_usuario"], 5))
    assert alcance.listar_ids_activos_permitidos(contador["id_usuario"], 5, id_finca=propia) == [en_propia]
    assert alcance.listar_ids_activos_permitidos(contador["id_usuario"], 5, id_finca=ajena) == []
    # El Administrador no tiene restricción: el filtro deja solo los activos de la finca pedida.
    assert alcance.listar_ids_activos_permitidos(contador["id_usuario"], 1, id_finca=ajena) == [en_ajena]


def test_listado_de_activos_por_finca_trae_la_finca(client, db_session, crear_usuario_db, crear_auth_headers):
    admin = crear_usuario_db(id_rol=1)
    finca = _finca(db_session, admin["id_usuario"], "Finca Listado Filtro")
    otra = _finca(db_session, admin["id_usuario"], "Finca Listado Otra")
    activo = _activo(db_session, finca, admin["id_usuario"])
    _activo(db_session, otra, admin["id_usuario"])

    headers = crear_auth_headers(admin)
    r = client.get("/activos-biologicos", params={"id_finca": finca, "page_size": 100}, headers=headers)
    assert r.status_code == 200, r.text
    registros = r.json()["registros"]
    assert [a["id_activo_biologico"] for a in registros] == [activo]
    assert (registros[0]["id_finca"], registros[0]["nombre_finca"]) == (finca, "Finca Listado Filtro")
    assert client.get("/activos-biologicos", params={"id_finca": 0}, headers=headers).status_code in (400, 422)

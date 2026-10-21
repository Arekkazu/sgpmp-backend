# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: área multiespecie contra la tabla puente de DB-06 (RFC-012) |
"""DEV-22 (RFC-012, RF-20): registrar/editar un área con varias especies escribe la
tabla puente ``modulo9.infraestructuras_especies`` (DB-06) y la capacidad se deriva.

Requiere la BD con DB-06 y DB-07 aplicadas.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


def _letras() -> str:
    return uuid4().hex[:10].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.configuration.infrastructure.routers.infraestructura_router import router as infraestructuras
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(infraestructuras)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers):
    sufijo = _letras()
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:n, '{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb, 10, now(), now(), true)
        RETURNING id_finca
    """), {"n": "Finca Multiespecie " + sufijo}).scalar_one()
    especies = {}
    for nombre, grupo, densidad in [("Mojarra", "ACUICULTURA", 100), ("Cachama", "ACUICULTURA", 100),
                                    ("Salmon", "ACUICULTURA", 80), ("Pollo", "AVES", 10)]:
        especies[nombre] = db_session.execute(text("""
            INSERT INTO modulo9.especies (nombre, es_activo, fecha_creacion, grupo_manejo, densidad_maxima_por_especie)
            VALUES (:n, true, now(), :g, :d) RETURNING id_especie
        """), {"n": f"{nombre} {sufijo}", "g": grupo, "d": densidad}).scalar_one()
    admin = crear_usuario_db(id_rol=1, estado=2)
    return {"finca": finca, "especies": especies, "headers": crear_auth_headers(admin), "sufijo": sufijo}


def _puente(db, area):
    return db.execute(text(
        "SELECT id_especie, fecha_creacion FROM modulo9.infraestructuras_especies "
        "WHERE id_infraestructura = :a ORDER BY id_infraestructuras_especies"
    ), {"a": area}).all()


def test_policultivo_se_registra_edita_y_lee_con_capacidad_derivada(cliente, db_session, escenario):
    e = escenario["especies"]
    r = cliente.post("/configuracion/infraestructuras", headers=escenario["headers"], json={
        "nombre_infraestructura": "Estanque " + escenario["sufijo"], "tipo_area": "Estanque",
        "superficie": "50", "finca_id": escenario["finca"],
        "especies": [e["Mojarra"], e["Cachama"], e["Salmon"]],
        "tipo_modelo_asignado": "MODELO_ACUICULTURA", "nivel_criticidad": "ALTA",
    })
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    area = cuerpo["id_infraestructura"]
    assert cuerpo["especies"] == [e["Mojarra"], e["Cachama"], e["Salmon"]]
    assert (cuerpo["capacidad_maxima"], cuerpo["nivel_criticidad"], cuerpo["especie_id"]) == (4000, "ALTA", None)
    filas = _puente(db_session, area)
    assert [f.id_especie for f in filas] == cuerpo["especies"]

    r = cliente.patch(f"/configuracion/infraestructuras/{area}", headers=escenario["headers"], json={
        "nombre_infraestructura": "Estanque " + escenario["sufijo"], "tipo_area": "Estanque",
        "superficie": "50", "especies": [e["Mojarra"], e["Cachama"]],
        "tipo_modelo_asignado": "MODELO_ACUICULTURA", "fecha_actualizacion": cuerpo["fecha_actualizacion"],
    })
    assert r.status_code == 200, r.text
    assert (r.json()["especies"], r.json()["capacidad_maxima"], r.json()["nivel_criticidad"]) == (
        [e["Mojarra"], e["Cachama"]], 5000, "ALTA")
    # Las filas que se quedan conservan su fecha de asociación (no delete-then-insert).
    assert _puente(db_session, area) == filas[:2]

    r = cliente.get(f"/configuracion/infraestructuras/{area}", headers=escenario["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["especies"] == [e["Mojarra"], e["Cachama"]]


def test_alias_especie_id_y_grupos_incompatibles(cliente, db_session, escenario):
    e = escenario["especies"]
    base = {"tipo_area": "Estanque", "superficie": "10", "finca_id": escenario["finca"]}
    r = cliente.post("/configuracion/infraestructuras", headers=escenario["headers"], json={
        **base, "nombre_infraestructura": "Alias " + escenario["sufijo"], "especie_id": e["Salmon"]})
    assert r.status_code == 201, r.text
    assert (r.json()["especies"], r.json()["especie_id"], r.json()["capacidad_maxima"]) == ([e["Salmon"]], e["Salmon"], 800)

    r = cliente.post("/configuracion/infraestructuras", headers=escenario["headers"], json={
        **base, "nombre_infraestructura": "Mezcla " + escenario["sufijo"], "especies": [e["Salmon"], e["Pollo"]]})
    assert r.status_code == 422, r.text
    assert r.json()["error_code"] == "GRUPOS_MANEJO_INCOMPATIBLES"


def test_m02_lee_las_especies_y_la_capacidad_del_area(db_session, escenario):
    from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter

    e = escenario["especies"]
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
        VALUES (:n, :f, 12.5, true, 'Estanque') RETURNING id_infraestructura
    """), {"n": "M02 " + escenario["sufijo"], "f": escenario["finca"]}).scalar_one()
    for especie in (e["Mojarra"], e["Salmon"]):
        db_session.execute(text(
            "INSERT INTO modulo9.infraestructuras_especies (id_infraestructura, id_especie) VALUES (:a, :e)"
        ), {"a": area, "e": especie})
    db_session.flush()

    infra = InfraestructuraM09Adapter(db_session).obtener_activa(area)

    assert infra.id_especies == [e["Mojarra"], e["Salmon"]]
    assert infra.capacidad_maxima == 1000  # floor(80 × 12.5)
    assert [x.densidad for x in infra.especies] == [Decimal("100"), Decimal("80")]

# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: bajar la densidad con un área llena → 422, contra la tabla puente de DB-06 |
"""DEV-21 (RFC-012): la densidad de una especie no baja por debajo de lo que dejaría un
área donde está con más individuos que su capacidad efectiva.

Requiere la BD con DB-06 y DB-07 aplicadas.
"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.configuration.infrastructure.routers.especie_router import router as especies
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(especies)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_reducir_densidad_con_area_llena(cliente, db_session, crear_usuario_db, crear_auth_headers):
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    sufijo = uuid4().hex[:10].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    especie = db_session.execute(text("""
        INSERT INTO modulo9.especies (nombre, es_activo, fecha_creacion, grupo_manejo, densidad_maxima_por_especie)
        VALUES (:n, true, now(), 'ESPECIES_GRANDES', 2) RETURNING id_especie
    """), {"n": "Bovino " + sufijo}).scalar_one()
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:n, '{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb, 10, now(), now(), true) RETURNING id_finca
    """), {"n": "Finca Densidad " + sufijo}).scalar_one()
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
        VALUES (:n, :f, 1, true, 'Corral') RETURNING id_infraestructura
    """), {"n": "Corral " + sufijo, "f": finca}).scalar_one()
    db_session.execute(text("INSERT INTO modulo9.infraestructuras_especies (id_infraestructura, id_especie) VALUES (:a, :e)"),
                       {"a": area, "e": especie})
    # El trigger de auditoría de M02 exige el usuario en la sesión.
    db_session.execute(text("SELECT set_config('app.usuario_id', :u, true)"), {"u": str(admin["id_usuario"])})
    # "pruebas" y una BD nueva pueden no traer el catálogo de estados.
    db_session.execute(text(
        "INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) "
        "VALUES (1, 'ACTIVO') ON CONFLICT (id_estado_activo_biologico) DO NOTHING"
    ))
    for i in range(2):  # carga 2 = capacidad floor(2 × 1)
        db_session.execute(text("""
            INSERT INTO modulo2.activos_biologicos (
                id_especie, identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado, descripcion,
                origen_financiero, costo_adquisicion, atributos_dinamicos, id_usuario, fecha_creacion,
                soporte_documental, detalles_procedencia
            ) VALUES (:e, :ident, :a, 'INDIVIDUAL', current_date, 1, 'DEV-21', 'compra', 100, '{}', :u, now(), 'doc', '')
        """), {"e": especie, "ident": f"DEV21-{sufijo}-{i}", "a": area, "u": admin["id_usuario"]})
    db_session.flush()
    nombre = "Bovino " + sufijo
    ts = db_session.execute(text("SELECT fecha_actualizacion FROM modulo9.especies WHERE id_especie = :e"),
                            {"e": especie}).scalar_one()

    r = cliente.patch(f"/configuracion/especies/{especie}", headers=headers, json={
        "nombre": nombre, "densidad_poblacional_max": "1.5", "fecha_actualizacion": ts.isoformat() if ts else None})
    assert r.status_code == 422, r.text
    assert r.json()["error_code"] == "DENSIDAD_DEJA_AREA_EXCEDIDA"

    r = cliente.patch(f"/configuracion/especies/{especie}", headers=headers, json={
        "nombre": nombre, "densidad_poblacional_max": "3", "fecha_actualizacion": ts.isoformat() if ts else None})
    assert r.status_code == 200, r.text
    assert r.json()["densidad_poblacional_max"] == r.json()["densidad_maxima_por_especie"]
    assert float(r.json()["densidad_poblacional_max"]) == 3

"""INC-M09-20-02 (RF-20): desactivar un área con un sensor asociado vigente cuyo
dispositivo está inactivo respondía 500.

La validación previa solo contaba dispositivos activos, así que dejaba pasar el
UPDATE; el trigger `trg_fn_infraestructura_no_desactivar_en_uso` sí cuenta los
sensores asociados y lanzaba P0127, que no estaba traducido.
"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


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


def test_area_con_sensor_asociado_de_dispositivo_inactivo_responde_422(
    cliente, db_session, crear_usuario_db, crear_auth_headers
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    sufijo = uuid4().hex[:12].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas
            (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:nombre, '{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb, 10, now(), now(), true)
        RETURNING id_finca
    """), {"nombre": "Finca Area En Uso " + sufijo}).scalar_one()
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:nombre,:finca,100,true,'Estanque') RETURNING id_infraestructura
    """), {"nombre": "Area En Uso " + sufijo, "finca": finca}).scalar_one()
    dispositivo = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot
            (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'Dispositivo INC-M09-20-02',true,now(),:area,1)
        RETURNING id_dispositivo_iot
    """), {"serial": "M0920-" + uuid4().hex, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores (id_dispositivo_iot,es_activo,nombre,categoria)
        VALUES (:dispositivo,true,:nombre,'TEMPERATURA') RETURNING id_sensores
    """), {"dispositivo": dispositivo, "nombre": "Sensor Area En Uso " + sufijo}).scalar_one()
    db_session.execute(text("""
        INSERT INTO modulo9.sensores_areas_asociadas
            (id_sensor,id_dispositivo_iot,id_infraestructura,punto_instalacion,
             tiene_estado,fecha_asociacion,id_usuario)
        VALUES (:sensor,:dispositivo,:area,'Punto INC-M09-20-02',true,now(),:usuario)
    """), {"sensor": sensor, "dispositivo": dispositivo, "area": area, "usuario": admin["id_usuario"]})
    # El escenario de QA: el dispositivo se apaga pero el sensor sigue asociado.
    db_session.execute(text(
        "UPDATE modulo9.dispositivos_iot SET es_activo = false WHERE id_dispositivo_iot = :d"
    ), {"d": dispositivo})

    r = cliente.patch(f"/configuracion/infraestructuras/{area}/desactivar", headers=crear_auth_headers(admin))

    assert r.status_code == 422, r.text
    assert r.json()["error_code"] == "INFRAESTRUCTURA_CON_DEPENDENCIAS"
    sigue_activa = db_session.execute(text(
        "SELECT es_activo FROM modulo9.infraestructuras WHERE id_infraestructura = :a"
    ), {"a": area}).scalar_one()
    assert sigue_activa is True

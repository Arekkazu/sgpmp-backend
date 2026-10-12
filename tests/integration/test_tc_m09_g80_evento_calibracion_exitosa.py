"""#508: integración PostgreSQL de calibración y evento RF-10.

Requiere TEST_DATABASE_URL y migración b6f2d8a40c91 aplicada. La transacción
exterior de db_session revierte las filas; las secuencias pueden avanzar.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente_g80(db_session, integration_app, monkeypatch):
    # integration_app registra los modelos de identidad y sus relaciones.
    from src.configuration.infrastructure.routers.sensor_router import router as sensores
    from src.identity_access.infrastructure.routers.auditoria_routers import router as auditoria
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.shared.middlewares import RequestContextMiddleware

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(sensores)
    app.include_router(auditoria)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


@pytest.fixture
def fixture_g80(db_session, crear_usuario_db, crear_auth_headers):
    catalogo = db_session.execute(text(
        "SELECT nombre FROM modulo1.tipos_eventos WHERE id_tipo_evento = 30"
    )).scalar_one_or_none()
    assert catalogo == "CALIBRACION_EXITOSA", "Aplicar alembic upgrade head en la base de integración."
    ingeniero = crear_usuario_db(id_rol=4, estado=2)
    admin = crear_usuario_db(id_rol=1, estado=2)
    sufijo = uuid4().hex[:12].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas
            (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:nombre, '{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb, 10, now(), now(), true)
        RETURNING id_finca
    """), {"nombre": "Finca Integracion Calibracion " + sufijo}).scalar_one()
    db_session.execute(text(
        "INSERT INTO modulo9.usuarios_fincas (id_usuario,id_finca) VALUES (:usuario,:finca)"
    ), {"usuario": ingeniero["id_usuario"], "finca": finca})
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:nombre,:finca,100,true,'Estanque') RETURNING id_infraestructura
    """), {"nombre": "Area Calibracion " + sufijo, "finca": finca}).scalar_one()
    dispositivo = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot
            (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'Dispositivo integracion G80',true,now(),:area,1)
        RETURNING id_dispositivo_iot
    """), {"serial": "G80-" + uuid4().hex, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores (id_dispositivo_iot,es_activo,nombre,categoria)
        VALUES (:dispositivo,true,:nombre,'TEMPERATURA') RETURNING id_sensores
    """), {"dispositivo": dispositivo, "nombre": "Sensor G80 " + sufijo}).scalar_one()
    db_session.execute(text("""
        INSERT INTO modulo9.sensores_areas_asociadas
            (id_sensor,id_dispositivo_iot,id_infraestructura,punto_instalacion,
             tiene_estado,fecha_asociacion,id_usuario)
        VALUES (:sensor,:dispositivo,:area,'Punto G80',true,now(),:usuario)
    """), {"sensor": sensor, "dispositivo": dispositivo, "area": area, "usuario": ingeniero["id_usuario"]})
    headers_ingeniero = crear_auth_headers(ingeniero)
    headers_admin = crear_auth_headers(admin)
    # Liberar el savepoint de setup, conservando la transacción exterior.
    db_session.commit()
    return dict(sensor=sensor, dispositivo=dispositivo, area=area,
                ingeniero=ingeniero, headers_ingeniero=headers_ingeniero,
                headers_admin=headers_admin)


def _body(fixture):
    return {"id_dispositivo_iot": fixture["dispositivo"], "id_infraestructura": fixture["area"],
            "valor_referencia": "22.5000", "modo_calibracion": "SENSOR",
            "fecha_calibracion": datetime.now(timezone.utc).isoformat()}


def test_calibracion_persistida_tiene_evento_rf10_consultable(cliente_g80, fixture_g80, db_session):
    f = fixture_g80
    inicio = datetime.now(timezone.utc) - timedelta(minutes=1)
    respuesta = cliente_g80.post(f"/configuracion/sensores/{f['sensor']}/calibrar",
                                json=_body(f), headers=f["headers_ingeniero"])
    fin = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert respuesta.status_code == 201, respuesta.text
    id_calibracion = respuesta.json()["id_calibracion"]
    historial = cliente_g80.get(f"/configuracion/sensores/{f['sensor']}/calibraciones",
                               headers=f["headers_ingeniero"])
    assert historial.status_code == 200, historial.text
    assert any(c["id_calibracion"] == id_calibracion for c in historial.json()["items"])
    auditoria = cliente_g80.get("/auditoria/", headers=f["headers_admin"], params={
        "id_usuario": f["ingeniero"]["id_usuario"], "tipo_evento": 30,
        "categoria": "MODIFICACION", "fecha_desde": inicio.isoformat(), "fecha_hasta": fin.isoformat(),
    })
    assert auditoria.status_code == 200, auditoria.text
    assert auditoria.json()["total"] == 1
    [evento] = auditoria.json()["items"]
    assert evento["resultado"] == "exitoso" and evento["integridad_ok"] is True
    assert inicio <= datetime.fromisoformat(evento["fecha_evento"]) <= fin
    assert evento["id_usuario"] == f["ingeniero"]["id_usuario"]
    assert evento["detalle"]["id_calibracion"] == id_calibracion
    assert evento["detalle"]["id_sensor"] == f["sensor"]
    assert evento["detalle"]["id_dispositivo_iot"] == f["dispositivo"]
    assert evento["detalle"]["valor_referencia"] == "22.5000"
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo9.auditorias_calibraciones WHERE id_calibracion=:id"
    ), {"id": id_calibracion}).scalar_one() == 1


def test_fallo_rf10_revierte_calibracion_y_auditoria_m09(cliente_g80, fixture_g80, db_session, monkeypatch):
    from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository

    original = SqlAlchemyEventoRepository.registrar

    def fallar(self, *args, **kwargs):
        if kwargs.get("tipo_evento") == 30:
            raise RuntimeError("Fallo simulado de RF-10")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(SqlAlchemyEventoRepository, "registrar", fallar)
    f = fixture_g80
    respuesta = cliente_g80.post(f"/configuracion/sensores/{f['sensor']}/calibrar",
                                json=_body(f), headers=f["headers_ingeniero"])
    assert respuesta.status_code == 500, respuesta.text
    assert respuesta.json()["error_code"] == "AUDITORIA_CALIBRACION_FALLIDA"
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo9.calibraciones WHERE id_sensor=:sensor"
    ), {"sensor": f["sensor"]}).scalar_one() == 0
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo9.auditorias_calibraciones WHERE id_usuario=:usuario"
    ), {"usuario": f["ingeniero"]["id_usuario"]}).scalar_one() == 0
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo1.eventos WHERE id_usuario=:usuario AND tipo_evento=30"
    ), {"usuario": f["ingeniero"]["id_usuario"]}).scalar_one() == 0

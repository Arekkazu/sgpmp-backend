"""DEV-04: triggers de las migraciones, repositorios y respuestas HTTP reales.

RF-53 y RF-57 usan sus routers públicos; una lectura obsoleta reproduce la
carrera de alerta. Inmutabilidad y
predicciones no tienen API de escritura en este checkout: se usa un endpoint
de prueba con SQL real y los handlers de producción, sin crear rutas producto.
"""
from datetime import datetime, timedelta, timezone
import importlib
import pkgutil
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.routers import alerta_router, telemetria_router
from src.shared.database import get_db, get_db_sistema

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    # Igual que el arranque de routers: registra los modelos referenciados por FK.
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models", "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def rechazos_sql(db_session):
    errores = []
    engine = db_session.get_bind().engine
    def capturar(contexto):
        original = contexto.original_exception
        errores.append((getattr(original, 'pgcode', None), getattr(getattr(original, 'diag', None), 'context', None)))
    event.listen(engine, 'handle_error', capturar)
    try:
        yield errores
    finally:
        event.remove(engine, 'handle_error', capturar)


@pytest.fixture
def hardware(db_session):
    tag = uuid.uuid4().hex[:12]
    area = db_session.execute(text("""
        WITH finca AS (
          INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
          VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    """), {"nombre": "Dev Cuatro " + ''.join(chr(97 + int(c,16)) for c in tag)}).scalar_one()
    device = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'DEV-04',true,now(),:area,3) RETURNING id_dispositivo_iot
    """), {"serial": tag, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Temperatura DEV Cuatro') RETURNING id_sensores
    """), {"device": device}).scalar_one()
    db_session.commit()  # Precondiciones ya existentes antes de la operación rechazada.
    return {"device": device, "sensor": sensor, "serial": tag, "area": area}


def _app():
    app = FastAPI()
    register_error_handlers(app)
    return app


def _payload(hardware, captura):
    return dict(device_id=hardware["device"], sensor_id=hardware["sensor"],
                serial=hardware["serial"], tipo_variable="TEMPERATURA_AMBIENTAL",
                valor="22.5000", unidad="°C", timestamp_captura=captura.isoformat())


def test_fecha_futura_la_rechaza_la_funcion_sql_con_su_bitacora(db_session, hardware, rechazos_sql, headers_broker):
    # Con la ingesta B+ (DEV-05) y DB-02, fn_ingesta_telemetria valida la fecha
    # antes de insertar: el trigger P0001 de telemetrias ya no se alcanza por
    # HTTP y la bitácora la escribe la función, no la aplicación.
    app = _app()
    app.include_router(telemetria_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    captura = datetime.now(timezone.utc) + timedelta(seconds=15)
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as client:
        response = client.post("/iot/telemetria", json=_payload(hardware, captura))
    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "ERROR_TIEMPO"
    assert db_session.execute(text("SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s"), {"s": hardware["sensor"]}).scalar_one() == 0
    rows = db_session.execute(text("SELECT estado_calidad::text,descripcion_text FROM modulo3.bitacora_ingest WHERE id_sensor=:s"), {"s": hardware["sensor"]}).all()
    assert len(rows) == 1
    assert rows[0][0] == "ERROR_TIEMPO" and "timestamp_captura" in rows[0][1]
    db_session.rollback()
    assert db_session.execute(text("SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_sensor=:s"), {"s": hardware["sensor"]}).scalar_one() == 1
    assert "modulo3" not in response.text and "P0001" not in response.text
    assert rechazos_sql == []


@pytest.mark.parametrize("operacion", ["UPDATE", "DELETE"])
def test_p0002_trigger_activo_y_handler_http(db_session, hardware, operacion, rechazos_sql):
    id_lectura = db_session.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
          timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,1,:d,22.5,now()-interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL','°C')
        RETURNING id_telemetria
    """), {"s": hardware["sensor"], "d": hardware["device"]}).scalar_one()
    db_session.commit()
    app = _app()

    @app.post("/operacion")
    def ejecutar():
        try:
            sql = "UPDATE modulo3.telemetrias SET valor_crudo=0 WHERE id_telemetria=:id" if operacion == "UPDATE" else "DELETE FROM modulo3.telemetrias WHERE id_telemetria=:id"
            db_session.execute(text(sql), {"id": id_lectura})
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/operacion")
    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "TELEMETRIA_INMUTABLE"
    assert rechazos_sql[0][0] == 'P0002'
    assert db_session.execute(text("SELECT valor_crudo FROM modulo3.telemetrias WHERE id_telemetria=:id"), {"id": id_lectura}).scalar_one() == 22.5
    assert db_session.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgname='trg_rf53_02_no_update'")).scalar_one() == 'O'


@pytest.mark.parametrize("fallo_auditoria", [None, "sql", "sin_id"])
def test_p0005_carrera_con_estado_vencida_no_modifica_historial(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, caplog, rechazos_sql, fallo_auditoria):
    from src.shared import jwt as jwt_module
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
    monkeypatch.setattr(jwt_module, '_SECRET_KEY', 'sgpmp-integration-tests-only')
    usuario = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(usuario)
    id_alerta = db_session.execute(text("""
        INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,tipo_variable,fecha_evento,fecha_generacion)
        VALUES ('FALLO_AMBIENTAL','LEVE','ACTIVA','EDGE','TEMPERATURA_AMBIENTAL',now(),now()) RETURNING id_alerta
    """)).scalar_one()
    repo = SqlAlchemyAlertaRepository(db_session)
    obsoleta = repo.obtener_por_id(id_alerta)
    db_session.execute(text("UPDATE modulo3.alertas SET estado_alerta='VENCIDA' WHERE id_alerta=:id"), {"id": id_alerta})
    db_session.commit()
    previo = db_session.execute(text("SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()
    monkeypatch.setattr(SqlAlchemyAlertaRepository, 'obtener_por_id', lambda self, _: obsoleta)
    if fallo_auditoria == "sql":
        def fallar(self, evento):
            db_session.execute(text('SELECT 1 / 0'))
        monkeypatch.setattr(SqlAlchemyBitacoraAuditoriaIotRepository, 'registrar', fallar)
    elif fallo_auditoria == "sin_id":
        monkeypatch.setattr(SqlAlchemyBitacoraAuditoriaIotRepository, 'registrar', lambda self, evento: evento)
    app = _app()
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=headers, json={"nuevo_estado":"EN_ATENCION", "motivo":"Prueba DEV-04"})
    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "TRANSICION_INVALIDA"
    assert rechazos_sql[0][0] == 'P0005'
    assert db_session.execute(text("SELECT estado_alerta::text FROM modulo3.alertas WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one() == "VENCIDA"
    assert db_session.execute(text("SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one() == previo
    eventos = db_session.execute(text("SELECT resultado::text,id_usuario,hash_integridad FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id=:id AND tipo_evento='TRANSICION_ALERTA_RECHAZADA'"), {"id": str(id_alerta)}).all()
    if fallo_auditoria:
        assert eventos == []
        assert 'no se pudo registrar el evento' in caplog.text
    else:
        assert len(eventos) == 1
        assert eventos[0][0] == 'RECHAZADO' and eventos[0][1] == usuario['id_usuario']
        assert len(eventos[0][2]) == 64


@pytest.mark.parametrize("existente,http,codigo", [(True,412,"MODELO_NO_ACTIVO"),(False,404,"VERSION_MODELO_NO_ENCONTRADA")])
def test_p0413_prediccion_real_sin_persistencia(db_session, existente, http, codigo, rechazos_sql):
    version = 2147483000
    if existente:
        version = db_session.execute(text("""
          INSERT INTO modulo4.versiones_modelos(tipo_modelo,nombre_version,fecha_entrenamiento,esta_produccion,
            estado_version,hash_artecfacto,hash_artefacto_sha256,ruta_artefacto,umbral_clasificacion)
          VALUES ('MODELO_ESPECIES_MEDIANAS',:v,now(),false,'EN_VALIDACION',:h,:h,'dev04.onnx',0.7)
          RETURNING id_version_modelo
        """), {"v": "0.0.0-dev04-"+uuid.uuid4().hex[:8], "h": "d"*64}).scalar_one()
    db_session.commit()
    previo = db_session.execute(text("SELECT count(*) FROM modulo4.predicciones")).scalar_one()
    app = _app()

    @app.post("/prediccion")
    def insertar():
        try:
            db_session.execute(text("INSERT INTO modulo4.predicciones(id_version_modelo,probabilidad_pct,umbral_usado) VALUES (:v,75,70)"), {"v": version})
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/prediccion")
    assert response.status_code == http, response.text
    assert response.json()["error_code"] == codigo
    assert rechazos_sql[0][0] == 'P0413'
    assert "P0413" not in response.text and "esta_produccion" not in response.text
    assert db_session.execute(text("SELECT count(*) FROM modulo4.predicciones")).scalar_one() == previo

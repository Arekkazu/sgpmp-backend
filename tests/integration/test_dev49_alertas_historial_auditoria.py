# | Fecha      | Nombre  | Que se hizo                                          |
# |------------|---------|------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: verifica flujos HTTP y triggers reales  |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-27/42: evaluador con parametros y lectura con lock |
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: ERROR_CALIBRACION genera alerta técnica FALLO_AMBIENTAL |
# | 2026-10-28 | destroyerban | INC-M03-163-G70 RF-57: el evento de temperatura lleva la humedad de su compuesta |
# | 2026-10-28 | destroyerban | INC-M03-173-G85 RF-57 E9: el caso de alerta operativa siembra su umbral RF-17 |
"""DEV-49 con JWT, broker, repositorios y PostgreSQL exclusivo de pruebas."""
from datetime import datetime, timedelta, timezone
import importlib
import importlib.util
from pathlib import Path
import pkgutil
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.alerta import AmbitoAlerta
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO
from src.telemetry.infrastructure.models.evento_edge_model import EventoEdgeComputingModel
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.routers import alerta_router, evento_edge_router

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos_dev49():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def hardware49(db_session):
    tag = uuid4().hex[:12]
    nombre = "Dev Cuarenta Nueve " + ''.join(chr(97 + int(c, 16)) for c in tag)
    area = db_session.execute(text("""
        WITH finca AS (
            INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
            VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    """), {"nombre": nombre}).scalar_one()
    device = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'DEV-49',true,now(),:area,3) RETURNING id_dispositivo_iot
    """), {"serial": tag, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Temperatura DEV Cuarenta Nueve') RETURNING id_sensores
    """), {"device": device}).scalar_one()
    db_session.commit()
    return {"device": device, "sensor": sensor, "area": area, "serial": tag}


@pytest.fixture
def http49(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, headers_broker):
    from src.shared import jwt as jwt_module
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    rol_admin = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Administrador'")).scalar_one()
    rol_vet = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Veterinario'")).scalar_one()
    rol_sin_alertas = db_session.execute(text("""
        INSERT INTO modulo1.roles(nombre_rol,es_protegido) VALUES (:nombre,false) RETURNING id_rol
    """), {"nombre": "DEV49 Sin alertas " + uuid4().hex[:10]}).scalar_one()
    db_session.execute(text("""
        INSERT INTO modulo1.permisos(nombre,id_rol,id_recurso,id_accion,es_activo)
        VALUES (:nombre,:rol,1,2,true)
    """), {"nombre": "DEV49 Base " + uuid4().hex[:10], "rol": rol_sin_alertas})
    usuarios = {"admin": crear_usuario_db(id_rol=rol_admin), "vet": crear_usuario_db(id_rol=rol_vet),
                "sin_permiso": crear_usuario_db(id_rol=rol_sin_alertas)}
    headers = {nombre: crear_auth_headers(usuario) for nombre, usuario in usuarios.items()}
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.include_router(evento_edge_router.router)

    def sesion():
        db_session.info.clear()
        return db_session

    app.dependency_overrides[get_db] = sesion
    app.dependency_overrides[get_db_sistema] = sesion
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, headers, usuarios, headers_broker


def _crear_alerta(db, estado="ACTIVA"):
    id_alerta = db.execute(text("""
        INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,tipo_variable,fecha_evento,fecha_generacion)
        VALUES ('FALLO_AMBIENTAL','LEVE',:estado,'EDGE','TEMPERATURA_AMBIENTAL',now(),now()) RETURNING id_alerta
    """), {"estado": estado}).scalar_one()
    db.commit()
    return id_alerta


def _historia(db, id_alerta):
    return db.execute(text("""
        SELECT estado_anterior::text,estado_nuevo::text,id_usuario,motivo,fecha_cambio
        FROM modulo3.historico_estados_alertas WHERE id_alerta=:id ORDER BY id_historico_estado_alerta
    """), {"id": id_alerta}).all()


def _fila_alerta(db, id_alerta):
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()


def _con_umbral_temperatura(db, area):
    especie = db.execute(text("SELECT min(id_especie) FROM modulo9.especies WHERE es_activo")).scalar_one()
    db.execute(text("INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES (:a,:e) "
                    "ON CONFLICT DO NOTHING"), {"a": area, "e": especie})
    if not db.execute(text("SELECT 1 FROM modulo9.umbrales_ambientales WHERE es_activo AND id_especie=:e "
                           "AND id_variable_ambiental=9"), {"e": especie}).first():
        db.execute(text("INSERT INTO modulo9.umbrales_ambientales(nombre,unidad_medida,es_activo,id_especie,"
                        "id_variable_ambiental,valor_min,valor_max) VALUES ('G85 temperatura','°C',true,:e,9,20,30)"),
                   {"e": especie})


def _lectura(db, hardware, calidad="LECTURA_VALIDA"):
    return db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
          timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,1,:d,38.5,:captura,now(),'TIEMPO_REAL',:calidad,'{}','AMBIENTAL','°C') RETURNING id_telemetria
    """), {"s": hardware["sensor"], "d": hardware["device"], "calidad": calidad,
           "captura": datetime.now(timezone.utc) - timedelta(minutes=1)}).scalar_one()


def _payload(hardware, id_lectura, calidad="LECTURA_VALIDA"):
    return {"device_id": hardware["device"], "sensor_id": hardware["sensor"], "serial": hardware["serial"],
            "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C",
            "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "estado_dato": calidad, "severidad_edge": "MODERADO", "origen_evento": "EDGE", "id_telemetria": id_lectura,
            # G70: ESTRES_TERMICO exige temperatura y humedad (THI ≥ 72); 38.5 °C y 60 % → THI 91.77.
            "correlacion_variables": {"HUMEDAD_RELATIVA": 60}}


def test_generacion_http_y_transiciones_generan_una_fila_cada_una(db_session, hardware49, http49):
    # G85 (RF-57 E9): sin umbral RF-17 para la variable en el área no hay alerta operativa.
    _con_umbral_temperatura(db_session, hardware49["area"])
    id_lectura = _lectura(db_session, hardware49)
    db_session.commit()
    client, headers, usuarios, broker = http49
    response = client.post("/iot/alertas", headers=broker, json=_payload(hardware49, id_lectura))
    assert response.status_code == 201, response.text
    id_alerta = response.json()["id_alerta"]
    inicial, = _historia(db_session, id_alerta)
    assert inicial[:2] == ("ACTIVA", "ACTIVA")
    for numero, (estado, usuario, motivo) in enumerate([
        ("EN_ATENCION", "admin", "Inspección inicial"), ("RESUELTA", "vet", "Diagnóstico y resolución"),
    ], 2):
        response = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=headers[usuario],
                                json={"nuevo_estado": estado, "motivo": motivo})
        assert response.status_code == 200, response.text
        filas = _historia(db_session, id_alerta)
        assert len(filas) == numero
        assert filas[-1][1:4] == (estado, usuarios[usuario]["id_usuario"], motivo)


def test_transicion_invalida_conserva_alerta_e_historia(db_session, http49):
    id_alerta = _crear_alerta(db_session)
    previo = _fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)
    response = http49[0].patch(f"/iot/alertas/{id_alerta}/estado", headers=http49[1]["admin"],
                               json={"nuevo_estado": "RESUELTA"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "TRANSICION_INVALIDA"
    assert (_fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)) == previo


def test_creacion_tecnica_una_fila_preserva_motivo(db_session, hardware49):
    estado = Mock(estado_actual="ACTIVO", id_dispositivo_iot=hardware49["device"],
                  fecha_ultimo_contacto=datetime.now(timezone.utc) - timedelta(days=2))
    estado.evaluar_transicion.return_value = "INACTIVO"
    # DEV-27: la transición se aplica sobre la entidad y los umbrales vienen del puerto.
    estado.aplicar_transicion.side_effect = lambda nuevo, *_: setattr(estado, "estado_actual", nuevo)
    estados, periodos, transiciones, historia = Mock(), Mock(), Mock(), Mock()
    estados.listar_activos.return_value = [estado]
    estados.bloquear_por_dispositivo.return_value = estado  # DEV-42: re-lee con lock
    periodos.obtener_abierto_por_dispositivo.return_value = None
    parametros = Mock()
    parametros.obtener_comunicacion.return_value = Mock(
        estado_local_buffer=None, umbral_activo=60, umbral_sin_senal=120, umbral_inactivo=600,
        id_infraestructura=None)
    caso = EvaluarEstadoDispositivosUseCase(db_session, estados, transiciones, periodos,
                                           SqlAlchemyAlertaRepository(db_session), historia, parametros)
    assert caso.execute() == 1
    id_alerta = db_session.execute(text("""
        SELECT id_alerta FROM modulo3.alertas WHERE id_dispositivo_ioit=:id AND tipo_alerta='TECNICA'
    """), {"id": hardware49["device"]}).scalar_one()
    registro, = _historia(db_session, id_alerta)
    assert registro[3] == "Dispositivo en estado INACTIVO"
    assert _fila_alerta(db_session, id_alerta)["metadato_evento"]["estado_operativo"] == "INACTIVO"
    historia.registrar.assert_not_called()


def test_error_commit_revierte_alerta_e_historia(db_session, crear_usuario_db, monkeypatch):
    usuario = crear_usuario_db()
    id_alerta = _crear_alerta(db_session)
    previo = _fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)
    repo = SqlAlchemyAlertaRepository(db_session)
    caso = ActualizarEstadoAlertaUseCase(db_session, repo, SqlAlchemyHistoricoEstadoAlertaRepository(db_session), AmbitoAlerta.OPERATIVA)
    original = db_session.commit
    monkeypatch.setattr(db_session, "commit", Mock(side_effect=RuntimeError("fallo inducido")))
    with pytest.raises(RuntimeError, match="inducido"):
        caso.execute(id_alerta, ActualizarEstadoAlertaDTO(nuevo_estado="EN_ATENCION", motivo="No persistir"), usuario["id_usuario"])
    monkeypatch.setattr(db_session, "commit", original)
    assert (_fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)) == previo


@pytest.mark.parametrize("metodo,sufijo", [("GET", ""), ("GET", "/{id}"), ("PATCH", "/{id}/estado")])
def test_403_persiste_bitacora_y_no_cambia_alerta(db_session, http49, metodo, sufijo):
    id_alerta = _crear_alerta(db_session)
    previo = _fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)
    client, headers, usuarios, _ = http49
    response = client.request(metodo, "/iot/alertas" + sufijo.format(id=id_alerta), headers=headers["sin_permiso"],
                              json={"nuevo_estado": "EN_ATENCION", "motivo": "NO_REGISTRAR_SECRETO"})
    assert response.status_code == 403, response.text
    assert response.json()["error_code"] == "ACCESO_DENEGADO"
    assert (_fila_alerta(db_session, id_alerta), _historia(db_session, id_alerta)) == previo
    eventos = db_session.execute(text("""
        SELECT resultado,id_usuario,entidad_afectada_id,accion_detallada,hash_integridad
        FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='ACCESO_DENEGADO' AND id_usuario=:usuario
    """), {"usuario": usuarios["sin_permiso"]["id_usuario"]}).all()
    evento, = eventos
    assert evento[0] == "RECHAZADO" and evento[1] == usuarios["sin_permiso"]["id_usuario"]
    assert evento[2] == (str(id_alerta) if sufijo else None)
    assert evento[3]["metodo"] == metodo and len(evento[4]) == 64
    assert "NO_REGISTRAR_SECRETO" not in str(evento)
    db_session.rollback()
    assert db_session.execute(text("""
        SELECT count(*) FROM modulo3.bitacora_auditoria_iot
        WHERE tipo_evento='ACCESO_DENEGADO' AND id_usuario=:usuario
    """), {"usuario": usuarios["sin_permiso"]["id_usuario"]}).scalar_one() == 1


@pytest.mark.parametrize("calidad", ["FUERA_DE_RANGO", "ERROR_CALIBRACION"])
def test_calidad_no_valida_conserva_lectura_y_registro_tecnico(db_session, hardware49, http49, calidad):
    id_lectura = _lectura(db_session, hardware49, calidad)
    db_session.commit()
    consulta = text("SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id")
    previo = db_session.execute(consulta, {"id": id_lectura}).scalar_one()
    response = http49[0].post("/iot/alertas", headers=http49[3], json=_payload(hardware49, id_lectura, calidad))
    assert response.status_code == 201, response.text
    assert db_session.execute(consulta, {"id": id_lectura}).scalar_one() == previo
    alertas = db_session.execute(text(
        "SELECT tipo_alerta, tipo_variable FROM modulo3.alertas WHERE id_telemetria=:id"), {"id": id_lectura}).all()
    if calidad == "ERROR_CALIBRACION":
        # INC-M03-162-G68: RF-57 FALLO_AMBIENTAL. No hay alerta operativa, pero sí la técnica para el ingeniero.
        assert response.json()["tipo_alerta"] == "TECNICA"
        assert [tuple(a) for a in alertas] == [("TECNICA", "FALLO_AMBIENTAL")]
    else:
        assert response.json()["id_alerta"] is None
        assert alertas == []
    evento, = db_session.execute(text("""
        SELECT clasificacion_registro,accion_detallada FROM modulo3.bitacora_auditoria_iot
        WHERE tipo_evento='LECTURA_EXCLUIDA_RF57' AND entidad_afectada_id=:id
    """), {"id": str(id_lectura)}).all()
    assert evento[0] == "TECNICO" and evento[1]["estado_dato"] == calidad


def test_edge_stub_persiste_paquete_alerta_e_historia_sin_repetir_diagnostico(db_session, hardware49, http49):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    payload = {"device_id": hardware49["device"], "sensor_id": hardware49["sensor"], "serial": hardware49["serial"],
        "clasificacion_rf55": "DESVIACION_SIMPLE", "severidad": "MODERADO", "timestamp_captura": ts,
        "timestamp_procesamiento_edge": ts, "estado_conectividad": True,
        "variables_involucradas": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"},
                                   {"tipo_variable": "HUMEDAD_RELATIVA", "valor": "90", "unidad": "%"}]}
    response = http49[0].post("/iot/eventos-edge", headers=http49[3], json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["paquete_inferencia_estado"] == "PENDIENTE"
    id_evento = response.json()["id_evento_edge_computing"]
    repo = SqlAlchemyPaqueteInferenciaRepository(db_session)
    paquete = repo.obtener_por_evento(id_evento)
    assert paquete.estado_paquete == "PENDIENTE" and paquete.intento_envios == 0
    alerta = db_session.execute(text("""
        SELECT id_alerta,tiene_inferencia_no_disponible,severidad::text,origen_evento::text
        FROM modulo3.alertas WHERE id_evento_edge_computing=:id
    """), {"id": id_evento}).one()
    assert alerta[1] is True and len(_historia(db_session, alerta[0])) == 1
    assert alerta[2:] == ("MODERADO", "EDGE")
    consulta_eventos = text("""
        SELECT resultado,accion_detallada FROM modulo3.bitacora_auditoria_iot
        WHERE tipo_evento='MOTOR_INFERENCIA_NO_INTEGRADO' AND entidad_afectada_id=:id
    """)
    registro, = db_session.execute(consulta_eventos, {"id": str(paquete.id_paquetes_inferencia)}).all()
    assert registro[0] == "ADVERTENCIA" and registro[1]["estado_paquete"] == "PENDIENTE"
    evento = SqlAlchemyEventoEdgeRepository._a_entidad(db_session.get(EventoEdgeComputingModel, id_evento))
    motor = Mock(wraps=MotorInferenciaStubAdapter())
    resultado = ConsolidarEnviarPaqueteUseCase(db_session, repo, motor, SqlAlchemyBitacoraAuditoriaIotRepository(db_session)).execute(evento)
    assert resultado.id_paquetes_inferencia == paquete.id_paquetes_inferencia
    motor.enviar_paquete.assert_not_called()
    assert len(db_session.execute(consulta_eventos, {"id": str(paquete.id_paquetes_inferencia)}).all()) == 1


def test_migracion_upgrade_downgrade_y_contexto_sin_fugas(db_session, crear_usuario_db):
    ruta = Path(__file__).parents[2] / "alembic/versions/6af49e8c2d10_dev49_rf57_motivo_historial_unico.py"
    spec = importlib.util.spec_from_file_location("migracion_dev49", ruta)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    usuario = crear_usuario_db()["id_usuario"]
    repo = SqlAlchemyAlertaRepository(db_session)
    for activa, esperado in [(False, None), (True, "Motivo preservado")]:
        with Operations.context(MigrationContext.configure(db_session.connection())):
            migracion.upgrade() if activa else migracion.downgrade()
        id_alerta = _crear_alerta(db_session)
        repo.actualizar_estado(id_alerta, "EN_ATENCION", usuario, "Motivo preservado")
        db_session.commit()
        assert _historia(db_session, id_alerta)[-1][3] == esperado
    # Una segunda operación sin motivo no hereda el contexto anterior.
    segundo = _crear_alerta(db_session)
    repo.actualizar_estado(segundo, "EN_ATENCION", usuario, None)
    db_session.commit()
    assert _historia(db_session, segundo)[-1][3] is None

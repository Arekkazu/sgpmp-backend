# | Fecha      | Nombre  | Que se hizo                                             |
# |------------|---------|---------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: verifica historial, 403 y eventos tecnicos |
# | 2026-10-25 | Arekkazu | INC-M03-137-G179 RF-63: cada paquete deja PAQUETE_INFERENCIA_GENERADO |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: un intento no confirmado queda PENDIENTE y se reprograma |
"""Pruebas de aplicación y HTTP con dobles explícitos, sin simular PostgreSQL."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthorizationError
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO
from src.telemetry.infrastructure.routers import alerta_router, ruta_alerta_auditada


def _alerta():
    ahora = datetime.now(timezone.utc)
    return Alerta(id_alerta=71, tipo_alerta="ESTRES_TERMICO", severidad="LEVE", estado_alerta="ACTIVA",
                  origen_evento="EDGE", tipo_variable="TEMPERATURA_AMBIENTAL", fecha_evento=ahora, fecha_generacion=ahora)


def _dto(estado="LECTURA_VALIDA"):
    return ProcesarEventoAlertaDTO(device_id=5, sensor_id=7, serial="DEV49", tipo_variable="TEMPERATURA_AMBIENTAL",
        valor="38.5", unidad="°C", timestamp_evento=datetime.now(timezone.utc), estado_dato=estado,
        severidad_edge="MODERADO", origen_evento="EDGE", id_telemetria=81,
        metadata_evento={"token": "NO_REGISTRAR_SECRETO"})


@pytest.fixture
def datos():
    db, repo, historia, auditoria = Mock(), Mock(), Mock(), Mock()
    eventos = []

    def registrar(evento):
        evento.id_evento = uuid4()
        eventos.append(evento)
        return evento

    auditoria.registrar.side_effect = registrar
    repo.obtener_por_id.side_effect = lambda _: deepcopy(_alerta())
    repo.buscar_activa_duplicada.return_value = None

    def guardar(alerta):
        alerta.id_alerta = 71
        return alerta

    repo.guardar.side_effect = guardar
    repo.actualizar_estado.side_effect = lambda **kw: Alerta(**(_alerta().__dict__ | {"estado_alerta": kw["nuevo_estado"]}))
    return db, repo, historia, auditoria, eventos


@pytest.fixture
def http(datos, monkeypatch):
    db, repo, historia, auditoria, eventos = datos
    permitido = {"valor": False}
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_: permitido["valor"])
    monkeypatch.setattr(alerta_router, "SqlAlchemyAlertaRepository", lambda _: repo)
    monkeypatch.setattr(alerta_router, "SqlAlchemyHistoricoEstadoAlertaRepository", lambda _: historia)
    monkeypatch.setattr(alerta_router, "SqlAlchemyBitacoraAuditoriaIotRepository", lambda _: auditoria)
    monkeypatch.setattr(ruta_alerta_auditada, "SqlAlchemyBitacoraAuditoriaIotRepository", lambda _: auditoria)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(43, 1, 971, 2)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, permitido


@pytest.mark.parametrize("metodo,ruta,accion", [
    ("GET", "/iot/alertas", 2), ("GET", "/iot/alertas/71", 2), ("PATCH", "/iot/alertas/71/estado", 3),
])
def test_403_en_dependencia_se_audita_una_vez(http, datos, metodo, ruta, accion):
    client, _ = http
    respuesta = client.request(metodo, ruta, json={"nuevo_estado": "EN_ATENCION", "motivo": "NO_REGISTRAR_SECRETO"},
                              headers={"Authorization": "Bearer NO_REGISTRAR_SECRETO"})
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    evento, = datos[4]
    assert evento.tipo_evento == "ACCESO_DENEGADO"
    assert evento.resultado == "RECHAZADO" and evento.id_usuario == 43
    assert evento.accion_detallada["id_accion"] == accion
    assert evento.accion_detallada["id_recurso"] == 32
    assert "NO_REGISTRAR_SECRETO" not in str(evento)
    datos[1].obtener_por_id.assert_not_called()
    datos[1].actualizar_estado.assert_not_called()
    datos[2].registrar.assert_not_called()
    datos[0].rollback.assert_called_once()
    datos[0].commit.assert_called_once()  # Solo la bitácora de rechazo.


def test_403_dentro_del_endpoint_tambien_se_audita(http, datos, monkeypatch):
    http[1]["valor"] = True
    caso = Mock()
    caso.execute.side_effect = AuthorizationError("ACCESO_DENEGADO", "Operación no autorizada")
    monkeypatch.setattr(alerta_router, "ActualizarEstadoAlertaUseCase", lambda **_: caso)
    respuesta = http[0].patch("/iot/alertas/71/estado", json={"nuevo_estado": "EN_ATENCION"})
    assert respuesta.status_code == 403
    assert len(datos[4]) == 1
    assert datos[4][0].entidad_afectada_id == "71"


def test_fallo_auditoria_no_oculta_403(http, datos):
    datos[3].registrar.side_effect = RuntimeError("NO_REGISTRAR_SECRETO")
    respuesta = http[0].patch("/iot/alertas/71/estado", json={"nuevo_estado": "EN_ATENCION"})
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    assert datos[4] == []
    datos[1].actualizar_estado.assert_not_called()
    datos[0].commit.assert_not_called()


def test_transicion_valida_no_insert_historial_desde_python(http, datos):
    http[1]["valor"] = True
    respuesta = http[0].patch("/iot/alertas/71/estado", json={"nuevo_estado": "EN_ATENCION", "motivo": "Revisión"})
    assert respuesta.status_code == 200, respuesta.text
    datos[2].registrar.assert_not_called()
    assert datos[4] == []


def test_400_no_se_registra_como_rechazo_403(http, datos):
    http[1]["valor"] = True
    respuesta = http[0].patch("/iot/alertas/71/estado", json={"nuevo_estado": "DESCONOCIDO"})
    assert respuesta.status_code == 400
    assert datos[4] == []


@pytest.mark.parametrize("calidad", ["FUERA_DE_RANGO", "ERROR_CALIBRACION"])
def test_calidad_invalida_conserva_diagnostico_y_no_genera_alerta(datos, calidad):
    db, repo, historia, auditoria, eventos = datos
    caso = GenararAlertaUseCase(db, repo, historia, Mock(), Mock(), auditoria)
    dto = _dto(calidad)
    previo = dto.model_dump()
    resultado = caso.execute(dto)
    assert resultado.id_alerta is None and calidad in resultado.motivo_descarte
    assert dto.model_dump() == previo
    repo.guardar.assert_not_called()
    repo.buscar_activa_duplicada.assert_not_called()
    historia.registrar.assert_not_called()
    evento, = eventos
    assert evento.tipo_evento == "LECTURA_EXCLUIDA_RF57"
    assert evento.clasificacion_registro == "TECNICO"
    assert evento.accion_detallada["estado_dato"] == calidad
    assert evento.entidad_afectada_id == "81"
    assert "NO_REGISTRAR_SECRETO" not in str(evento)


def test_generar_alerta_valida_deja_historial_al_trigger(datos):
    db, repo, historia, auditoria, eventos = datos
    resultado = GenararAlertaUseCase(db, repo, historia, Mock(), Mock(), auditoria).execute(_dto())
    assert resultado.id_alerta == 71
    historia.registrar.assert_not_called()
    assert eventos == []


@pytest.fixture
def motor_datos(datos):
    db, _, _, auditoria, eventos = datos
    repo = Mock()
    repo.obtener_por_evento.return_value = None

    def guardar(paquete):
        paquete.id_paquetes_inferencia = 19
        return paquete

    repo.guardar.side_effect = guardar
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    evento = EventoEdgeComputing(id_evento_edge_computing=17, id_sensor=7, id_dispositivo_iot=5,
        clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA", severidad="MODERADO",
        fecha_captura=ts, fecha_procesamiento=ts, origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"}])
    return db, repo, auditoria, eventos, evento


@pytest.mark.parametrize("resultado,tipo_evento,estado", [
    (True, None, "ENVIADO"),
    # INC-M03-113-G56: el intento 1 no confirmado queda PENDIENTE; el fallo se registra igual.
    (False, "ENVIO_INFERENCIA_NO_CONFIRMADO", "PENDIENTE"),
    (TimeoutError("NO_REGISTRAR_SECRETO"), "MOTOR_INFERENCIA_NO_DISPONIBLE", "PENDIENTE"),
    (RuntimeError("NO_REGISTRAR_SECRETO"), "ERROR_ENVIO_INFERENCIA", "PENDIENTE"),
])
def test_distingue_entrega_fallida_indisponibilidad_y_error(motor_datos, resultado, tipo_evento, estado):
    db, repo, auditoria, eventos, evento = motor_datos
    motor = Mock()
    if isinstance(resultado, Exception):
        motor.enviar_paquete.side_effect = resultado
    else:
        motor.enviar_paquete.return_value = resultado
    paquete = ConsolidarEnviarPaqueteUseCase(db, repo, motor, auditoria).execute(evento)
    assert paquete.estado_paquete == estado
    generado, *fallos = eventos
    assert generado.tipo_evento == "PAQUETE_INFERENCIA_GENERADO" and generado.componente_origen == "RF56"
    if tipo_evento is None:
        assert fallos == []
    else:
        registro, = fallos
        assert registro.tipo_evento == tipo_evento and registro.resultado == "FALLIDO"
        assert registro.accion_detallada["estado_paquete"] == estado
        assert "NO_REGISTRAR_SECRETO" not in str(registro)


def test_stub_y_reconsolidacion_no_duplican_evento_ni_entrega(motor_datos):
    db, repo, auditoria, eventos, evento = motor_datos
    motor = Mock(wraps=MotorInferenciaStubAdapter())
    caso = ConsolidarEnviarPaqueteUseCase(db, repo, motor, auditoria)
    paquete = caso.execute(evento)
    assert paquete.estado_paquete == "PENDIENTE" and paquete.intento_envios == 0
    generado, registro = eventos
    assert generado.tipo_evento == "PAQUETE_INFERENCIA_GENERADO"
    assert registro.tipo_evento == "MOTOR_INFERENCIA_NO_INTEGRADO"
    assert registro.accion_detallada["estado_paquete"] == "PENDIENTE"
    repo.obtener_por_evento.return_value = paquete
    assert caso.execute(evento) is paquete
    assert len(eventos) == 2  # reconsolidar no genera otro paquete ni otro evento
    motor.enviar_paquete.assert_called_once()


def test_fallo_persistencia_no_genera_evento_motor(motor_datos):
    db, repo, auditoria, eventos, evento = motor_datos
    repo.guardar.side_effect = RuntimeError("Persistencia")
    motor = Mock()
    with pytest.raises(RuntimeError):
        ConsolidarEnviarPaqueteUseCase(db, repo, motor, auditoria).execute(evento)
    assert eventos == []
    motor.enviar_paquete.assert_not_called()


def test_fallo_auditoria_no_pierde_paquete_pendiente(motor_datos):
    db, repo, auditoria, eventos, evento = motor_datos
    auditoria.registrar.side_effect = RuntimeError("Auditoría")
    paquete = ConsolidarEnviarPaqueteUseCase(db, repo, MotorInferenciaStubAdapter(), auditoria).execute(evento)
    assert paquete.estado_paquete == "PENDIENTE"
    assert eventos == []
    db.commit.assert_called_once()  # El paquete ya estaba confirmado antes del log.

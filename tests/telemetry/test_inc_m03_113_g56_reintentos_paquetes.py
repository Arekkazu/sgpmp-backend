# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
"""INC-M03-113-G56 (RF-56 restricción 14, E4, E5, CA-6, CA-14): reintentos y cola de reenvío.

Todas estas pruebas usan DOBLES del motor de inferencia (Mock del puerto o el stub). Ninguna
demuestra una integración real con M04, que no existe (ver INC-M03-112-G55): prueban la
política de estados, las esperas y el orden de la cola del lado del backend.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY, Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, Session

from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.application.use_cases.inferencia.drenar_paquetes_pendientes_use_case import DrenarPaquetesPendientesUseCase
from src.telemetry.domain.entities.telemetria import (
    ESPERAS_REINTENTO_INFERENCIA_SEG,
    MAX_INTENTOS_ENVIO_INFERENCIA,
    EventoEdgeComputing,
    estado_tras_envio_fallido,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort, MotorInferenciaRechazoError
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.repositories import paquete_inferencia_repository as repo_mod
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.workers import reenvio_inferencia_worker as worker
from tests.telemetry.test_inc_m03_112_g55_paquetes_inferencia import _RepoMemoria

_T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def _drenar(repo, motor):
    return DrenarPaquetesPendientesUseCase(Mock(), repo, motor).execute()


def test_politica_es_5_intentos_con_esperas_de_rf56():
    assert ESPERAS_REINTENTO_INFERENCIA_SEG == (0, 5, 15, 30, 60)
    assert MAX_INTENTOS_ENVIO_INFERENCIA == 5
    assert [estado_tras_envio_fallido(n) for n in range(1, 6)] == ["PENDIENTE"] * 4 + ["FALLIDO"]


def test_cinco_intentos_respetan_las_esperas_y_el_quinto_deja_fallido():
    """Intento 1 inmediato; 2..5 a los 5, 15, 30 y 60 s del anterior; nunca antes ni un sexto."""
    repo = _RepoMemoria(1)
    repo.ahora = _T0
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_lote.return_value = False
    instantes = []

    def registrar(lote):
        instantes.append(repo.ahora)
        return False

    motor.enviar_lote.side_effect = registrar
    _drenar(repo, motor)                                   # intento 1, inmediato
    for espera in ESPERAS_REINTENTO_INFERENCIA_SEG[1:]:
        repo.ahora += timedelta(seconds=espera - 1)
        _drenar(repo, motor)                               # un segundo antes: no se intenta
        repo.ahora += timedelta(seconds=1)
        _drenar(repo, motor)                               # al vencer: siguiente intento
    repo.ahora += timedelta(hours=1)
    _drenar(repo, motor)                                   # agotado: no hay sexto intento

    paquete, = repo.paquetes.values()
    assert [int((t - _T0).total_seconds()) for t in instantes] == [0, 5, 20, 50, 110]
    assert paquete.estado_paquete == "FALLIDO" and paquete.intento_envios == 5


def test_rechazo_del_motor_deja_fallido_sin_reintentos():
    repo = _RepoMemoria(2)
    repo.ahora = _T0
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_lote.side_effect = MotorInferenciaRechazoError("esquema invalido")
    resultado = _drenar(repo, motor)
    repo.ahora += timedelta(hours=1)
    _drenar(repo, motor)
    assert resultado.fallidos == 2 and resultado.reprogramados == 0
    assert repo.estados() == {"FALLIDO"} and motor.enviar_lote.call_count == 1


def test_m04_no_disponible_antes_del_primer_intento_deja_pendiente():
    """E4 / CA-5: sin motor no hay intento; el paquete sigue PENDIENTE con 0 intentos."""
    repo = _RepoMemoria(3)
    resultado = _drenar(repo, MotorInferenciaStubAdapter())
    assert resultado.motor_integrado is False
    assert repo.estados() == {"PENDIENTE"} and {p.intento_envios for p in repo.paquetes.values()} == {0}


def test_al_recuperar_m04_reenvia_los_pendientes_en_orden_cronologico():
    """CA-6: primero sin motor (stub), luego disponible: salen todos, en orden de captura."""
    repo = _RepoMemoria(4)
    repo.ahora = _T0
    _drenar(repo, MotorInferenciaStubAdapter())
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_lote.return_value = True
    resultado = _drenar(repo, motor)
    lote, = [c.args[0] for c in motor.enviar_lote.call_args_list]
    assert [p.id_paquetes_inferencia for p in lote] == [1, 2, 3, 4]
    assert resultado.enviados == 4 and repo.estados() == {"ENVIADO"}


def test_tras_caida_temporal_la_cola_reenvia_en_orden_cuando_vence_la_espera():
    repo = _RepoMemoria(3)
    repo.ahora = _T0
    caido = Mock(spec=MotorInferenciaPort)
    caido.enviar_lote.side_effect = ConnectionError("M04 caido")
    assert _drenar(repo, caido).reprogramados == 3
    repo.ahora += timedelta(seconds=5)
    sano = Mock(spec=MotorInferenciaPort)
    sano.enviar_lote.return_value = True
    _drenar(repo, sano)
    lote, = [c.args[0] for c in sano.enviar_lote.call_args_list]
    assert [p.id_paquetes_inferencia for p in lote] == [1, 2, 3]
    assert repo.estados() == {"ENVIADO"} and {p.intento_envios for p in repo.paquetes.values()} == {2}


@pytest.fixture
def evento():
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    return EventoEdgeComputing(
        id_evento_edge_computing=7, id_sensor=3, id_dispositivo_iot=2,
        clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA", severidad="MODERADO",
        fecha_captura=ts, fecha_procesamiento=ts, origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"}],
    )


@pytest.mark.parametrize("respuesta, estado", [
    ({"return_value": True}, "ENVIADO"),
    ({"return_value": False}, "PENDIENTE"),
    ({"side_effect": TimeoutError("M04")}, "PENDIENTE"),
    ({"side_effect": MotorInferenciaRechazoError()}, "FALLIDO"),
])
def test_consolidacion_hace_el_intento_1_y_aplica_la_politica(evento, respuesta, estado):
    repo = Mock(spec=PaqueteInferenciaRepository)
    repo.obtener_por_evento.return_value = None

    def guardar(paquete):
        paquete.id_paquetes_inferencia = 11
        return paquete

    repo.guardar.side_effect = guardar
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_paquete.configure_mock(**respuesta)
    paquete = ConsolidarEnviarPaqueteUseCase(Mock(), repo, motor).execute(evento)
    assert paquete.estado_paquete == estado and paquete.intento_envios == 1
    repo.actualizar_estado.assert_called_once_with(11, estado, 1, ANY)
    assert isinstance(repo.actualizar_estado.call_args.args[3], datetime)


def test_listar_pendientes_filtra_por_espera_vencida(monkeypatch):
    capturado = {}

    def all_(query):
        capturado["sql"] = " ".join(str(query.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split())
        return []

    monkeypatch.setattr(Query, "all", all_)
    SqlAlchemyPaqueteInferenciaRepository(Session()).listar_pendientes(500)
    sql = capturado["sql"]
    assert "modulo3.paquetes_inferencia.intento_envios = 0" in sql
    assert "make_interval(0, 0, 0, 0, 0, 0, CASE modulo3.paquetes_inferencia.intento_envios" in sql
    assert "WHEN 1 THEN 5 WHEN 2 THEN 15 WHEN 3 THEN 30 WHEN 4 THEN 60 ELSE 60 END" in sql
    assert "<= now()" in sql


def _orm(estado="PENDIENTE", intentos=1):
    return SimpleNamespace(id_paquetes_inferencia=11, estado_paquete=estado, intento_envios=intentos,
                           fecha_envio=_T0, id_evento_edge_computing=7, id_dispositivo_iot=2)


@pytest.mark.parametrize("estado, intento, tipo", [
    ("PENDIENTE", 2, "REINTENTO_ENVIO_PAQUETE_PROGRAMADO"),
    ("FALLIDO", 5, "FALLO_ENVIO_PAQUETE"),
    ("ENVIADO", 2, "PAQUETE_ENVIADO_IA"),
])
def test_repositorio_registra_la_transicion_y_la_fecha_del_intento(monkeypatch, estado, intento, tipo):
    orm = _orm()
    db = Mock()
    db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = orm
    registrados = []
    monkeypatch.setattr(repo_mod, "registrar_evidencia", lambda _r, t, *a, **kw: registrados.append((t, kw["detalle"])))
    fecha = _T0 + timedelta(seconds=5)
    SqlAlchemyPaqueteInferenciaRepository(db).actualizar_estado(11, estado, intento, fecha)
    assert (orm.estado_paquete, orm.intento_envios, orm.fecha_envio) == (estado, intento, fecha)
    (registrado, detalle), = registrados
    assert registrado == tipo and detalle["intentos"] == intento


def test_worker_drena_con_el_adaptador_configurado_y_cierra_la_sesion(monkeypatch):
    db = Mock()
    monkeypatch.setattr(worker, "sesion_sistema", lambda: db)
    usados = {}

    class _Drenar:
        def __init__(self, **kw):
            usados.update(kw)

        def execute(self):
            usados["ejecutado"] = True

    monkeypatch.setattr(worker, "DrenarPaquetesPendientesUseCase", _Drenar)
    worker.drenar_una_vez()
    assert usados["ejecutado"] and isinstance(usados["motor_inferencia_port"], MotorInferenciaStubAdapter)
    db.close.assert_called_once()

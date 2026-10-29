# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-118-G61 RF-55: latencia de deteccion medida en el Edge y SLA de 500 ms |
"""INC-M03-118-G61 (RF-55 restricción 1, CA-1): evidencia por evento del SLA de detección en el Edge.

El backend NO mide al Edge: calcula timestamp_procesamiento_edge − timestamp_captura, que son
instantes del reloj del nodo. TC-M03-123 sigue bloqueado hasta que el edge_agent implemente
RF-55 (hoy solo hay un simulador de datos, FakeLoraSource).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as edge
from src.telemetry.domain.entities.telemetria import LATENCIA_MAX_MS_RF55, latencia_edge_ms
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.schema.evento_edge_schema import EventoEdgeResponse

_T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def test_el_limite_de_rf55_es_500_ms():
    assert LATENCIA_MAX_MS_RF55 == 500


@pytest.mark.parametrize("ms", [0, 1, 250, 499, 500, 501, 60000])
def test_latencia_es_procesamiento_menos_captura_en_ms(ms):
    assert latencia_edge_ms(_T0, _T0 + timedelta(milliseconds=ms)) == ms


def _ejecutar(monkeypatch, ms, metadata_edge=None):
    consolidar = Mock()
    consolidar.execute.return_value = None
    monkeypatch.setattr(edge, "ConsolidarEnviarPaqueteUseCase", lambda **kw: consolidar)
    monkeypatch.setattr(edge.RecibirEventoEdgeUseCase, "_generar_alerta_best_effort", lambda *a, **k: None)
    guardados = []

    def guardar(entidad):
        entidad.id_evento_edge_computing = 12
        guardados.append(entidad)
        return entidad

    eventos = Mock()
    eventos.guardar.side_effect = guardar
    dispositivos = Mock()
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9, es_activo_dispositivo=True, es_activo_sensor=True)
    captura = datetime.now(timezone.utc) - timedelta(seconds=5)
    dto = RecibirEventoEdgeDTO(
        device_id=3, sensor_id=7, serial="SERIAL-TEST", clasificacion_rf55="DESVIACION_SIMPLE", severidad="LEVE",
        variables_involucradas=[{"tipo_variable": "NH3", "valor": 30, "unidad": "ppm"}],
        timestamp_captura=captura, timestamp_procesamiento_edge=captura + timedelta(milliseconds=ms),
        estado_conectividad=True, metadata_edge=metadata_edge)
    resultado = edge.RecibirEventoEdgeUseCase(Mock(), eventos, Mock(), dispositivos, Mock(), Mock(), Mock()).execute(dto)
    return guardados[0], resultado


@pytest.mark.parametrize("ms, excedido", [(120, False), (500, False), (501, True), (1500, True)])
def test_evento_guarda_y_devuelve_la_evidencia_del_sla(monkeypatch, ms, excedido):
    """Exactamente 500 ms cumple: RF-55 dice ≤ 500 ms."""
    entidad, resultado = _ejecutar(monkeypatch, ms)
    assert entidad.metadatos["latencia_edge_ms"] == ms
    assert entidad.metadatos["sla_edge_excedido"] is excedido
    assert (resultado.latencia_edge_ms, resultado.sla_edge_excedido) == (ms, excedido)


def test_conserva_la_metadata_del_edge_y_prevalece_el_calculo_del_backend(monkeypatch):
    entidad, _ = _ejecutar(monkeypatch, 800, metadata_edge={"firmware": "1.2.0", "latencia_edge_ms": 10,
                                                             "sla_edge_excedido": False})
    assert entidad.metadatos["firmware"] == "1.2.0"
    assert (entidad.metadatos["latencia_edge_ms"], entidad.metadatos["sla_edge_excedido"]) == (800, True)


def test_respuesta_http_expone_la_latencia():
    datos = EventoEdgeResponse(
        id_evento_edge_computing=1, clasificacion_rf55="NORMAL", severidad=None, estado_conectividad=True,
        fecha_captura=_T0, fecha_procesamiento=_T0 + timedelta(milliseconds=320), paquete_inferencia_estado=None,
        latencia_edge_ms=320, sla_edge_excedido=False).model_dump()
    assert (datos["latencia_edge_ms"], datos["sla_edge_excedido"]) == (320, False)

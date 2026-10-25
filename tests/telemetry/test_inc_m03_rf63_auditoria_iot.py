# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M03-135/137/147 RF-63: incompletos, E8, verificación y RF-55 |
"""RF-63 (bitácora IoT):

- INC-M03-147-G191 CA-13: un evento sin tipo o sin RF emisor se registra, marcado incompleto.
- INC-M03-137-G179 E8: sin RF emisor identificable la clasificación es NIC41 (5 años);
  RF-55 deja DESVIACION_DETECTADA / EVENTO_COMPUESTO_GENERADO en la bitácora.
- INC-M03-135-G177: la verificación de integridad no recorre la bitácora completa.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.shared.errors import BusinessRuleError, ValidationError
from src.telemetry.application.use_cases.auditoria import verificar_integridad_bitacora_use_case as verificar
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    TIPO_EVENTO_NO_INFORMADO,
    RegistrarEventoAuditoriaIotUseCase,
    _calcular_hash,
)
from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as edge
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, TipoResultado
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO


class _Bitacora:
    def __init__(self, eventos=()):
        self.eventos = list(eventos)
        self.limites = []

    def registrar(self, evento):
        nuevo = replace(evento, id_evento=uuid4())
        self.eventos.append(nuevo)
        return nuevo

    def listar_todos_para_verificacion(self, desde=None, hasta=None, limite=None):
        self.limites.append(limite)
        return self.eventos[:limite]


@pytest.mark.parametrize("tipo, componente, faltantes", [
    (None, ComponenteOrigen.RF53, ["tipo_evento"]),
    ("TELEMETRIA_RECIBIDA", None, ["rf_origen"]),
    ("", None, ["tipo_evento", "rf_origen"]),
])
def test_evento_incompleto_se_registra_sin_rechazarse(tipo, componente, faltantes):
    bitacora = _Bitacora()
    RegistrarEventoAuditoriaIotUseCase(Mock(), bitacora).execute(
        tipo_evento=tipo, resultado=TipoResultado.EXITOSO, componente_origen=componente,
        accion_detallada={"id_telemetria": 7})
    evento, = bitacora.eventos
    assert evento.registro_incompleto is True
    assert evento.accion_detallada == {"id_telemetria": 7, "campos_faltantes": faltantes}
    assert evento.tipo_evento == (tipo or TIPO_EVENTO_NO_INFORMADO)
    assert evento.hash_integridad == _calcular_hash(evento)
    if componente is None:  # E8: ambiguo → NIC41 con la retención más larga
        assert (evento.clasificacion_registro, evento.retencion_aplicable) == ("NIC41", 5)


def test_evento_completo_conserva_fecha_del_evento_y_no_es_incompleto():
    bitacora = _Bitacora()
    cuando = datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
    RegistrarEventoAuditoriaIotUseCase(Mock(), bitacora).execute(
        tipo_evento="TELEMETRIA_RECIBIDA", resultado=TipoResultado.EXITOSO,
        componente_origen=ComponenteOrigen.RF60, fecha_evento=cuando)
    evento, = bitacora.eventos
    assert (evento.fecha_hora, evento.registro_incompleto, evento.accion_detallada) == (cuando, False, None)
    assert (evento.clasificacion_registro, evento.retencion_aplicable) == ("TECNICO", 1)


def test_verificacion_de_un_rango_con_demasiados_eventos_se_rechaza(monkeypatch):
    monkeypatch.setattr(verificar, "MAX_EVENTOS_VERIFICACION", 2)
    bitacora = _Bitacora()
    for _ in range(3):
        RegistrarEventoAuditoriaIotUseCase(Mock(), bitacora).execute(
            tipo_evento="X", resultado=TipoResultado.EXITOSO, componente_origen=ComponenteOrigen.RF53)
    with pytest.raises(BusinessRuleError) as exc:
        verificar.VerificarIntegridadBitacoraUseCase(Mock(), bitacora).execute(
            datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 12, 31, tzinfo=timezone.utc))
    assert exc.value.code == "RANGO_VERIFICACION_EXCEDIDO"
    assert bitacora.limites == [3]  # nunca pide más de máximo + 1


def test_verificacion_con_rango_invertido_se_rechaza():
    with pytest.raises(ValidationError) as exc:
        verificar.VerificarIntegridadBitacoraUseCase(Mock(), _Bitacora()).execute(
            datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert exc.value.code == "RANGO_FECHAS_INVALIDO"


@pytest.mark.parametrize("clasificacion, tipo", [
    ("DESVIACION_SIMPLE", "DESVIACION_DETECTADA"),
    ("DESVIACION_COMPUESTA", "EVENTO_COMPUESTO_GENERADO"),
    ("NORMAL", None),
])
def test_rf55_deja_su_evento_en_la_bitacora(monkeypatch, clasificacion, tipo):
    consolidar = Mock()
    consolidar.execute.return_value = None
    monkeypatch.setattr(edge, "ConsolidarEnviarPaqueteUseCase", lambda **kw: consolidar)
    monkeypatch.setattr(edge.RecibirEventoEdgeUseCase, "_generar_alerta_best_effort", lambda *a, **k: None)
    eventos = Mock()

    def guardar_evento(entidad):
        entidad.id_evento_edge_computing = 12
        return entidad

    eventos.guardar.side_effect = guardar_evento
    dispositivos = Mock()
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9, es_activo_dispositivo=True, es_activo_sensor=True)
    bitacora = _Bitacora()
    ahora = datetime.now(timezone.utc) - timedelta(seconds=5)
    edge.RecibirEventoEdgeUseCase(Mock(), eventos, Mock(), dispositivos, Mock(), Mock(), bitacora).execute(
        RecibirEventoEdgeDTO(device_id=3, sensor_id=7, serial="SERIAL-TEST", clasificacion_rf55=clasificacion,
                             severidad="LEVE", variables_involucradas=[{"tipo_variable": "NH3", "valor": 25, "unidad": "ppm"}],
                             timestamp_captura=ahora, timestamp_procesamiento_edge=ahora, estado_conectividad=True))
    tipos = [e.tipo_evento for e in bitacora.eventos]
    assert tipos == ([tipo] if tipo else [])
    if tipo:
        evento, = bitacora.eventos
        assert evento.componente_origen == "RF55" and evento.clasificacion_registro == "TECNICO"
        assert evento.accion_detallada["id_evento_edge_computing"] == 12

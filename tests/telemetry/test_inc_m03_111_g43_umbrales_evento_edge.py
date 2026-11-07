# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-111-G43 RF-55.1: guarda valor y umbrales aplicados por el Edge |
"""INC-M03-111-G43 (RF-55.1): el evento Edge conserva el valor evaluado y los umbrales aplicados.

La clasificación NORMAL / DESVIACION_SIMPLE la calcula el Edge; el backend no la recalcula,
pero guarda con qué valor y con qué umbrales se tomó, como evidencia de TC-M03-076/077/078.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as edge
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository


def _dto(**extra) -> RecibirEventoEdgeDTO:
    ahora = datetime.now(timezone.utc) - timedelta(seconds=5)
    valor = extra.get("valor_evaluado", 25)
    return RecibirEventoEdgeDTO(
        device_id=3, sensor_id=7, serial="SERIAL-TEST", clasificacion_rf55=extra.pop("clasificacion", "NORMAL"),
        variables_involucradas=[{"tipo_variable": "NH3", "valor": valor, "unidad": "ppm"}],
        timestamp_captura=ahora, timestamp_procesamiento_edge=ahora, estado_conectividad=True, **extra)


def _ejecutar(monkeypatch, dto):
    consolidar = Mock()
    consolidar.execute.return_value = None
    monkeypatch.setattr(edge, "ConsolidarEnviarPaqueteUseCase", lambda **kw: consolidar)
    monkeypatch.setattr(edge.RecibirEventoEdgeUseCase, "_generar_alerta_best_effort", lambda *a, **k: None)
    eventos = Mock()
    guardados = []

    def guardar_evento(entidad):
        entidad.id_evento_edge_computing = 12
        guardados.append(entidad)
        return entidad

    eventos.guardar.side_effect = guardar_evento
    dispositivos = Mock()
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9, es_activo_dispositivo=True, es_activo_sensor=True)
    resultado = edge.RecibirEventoEdgeUseCase(
        Mock(), eventos, Mock(), dispositivos, Mock(), Mock(), Mock()).execute(dto)
    return guardados[0], resultado


@pytest.mark.parametrize("caso, clasificacion, valor", [
    ("TC-M03-076", "NORMAL", "25"),
    ("TC-M03-077", "DESVIACION_SIMPLE", "35"),
    ("TC-M03-078", "DESVIACION_SIMPLE", "5"),
])
def test_evento_conserva_valor_y_umbrales_del_edge(monkeypatch, caso, clasificacion, valor):
    dto = _dto(clasificacion=clasificacion, valor_evaluado=Decimal(valor),
               umbral_min_aplicado=Decimal("10"), umbral_max_aplicado=Decimal("30"))
    entidad, resultado = _ejecutar(monkeypatch, dto)
    for obj in (entidad, resultado):
        assert obj.clasificacion_rf55 == clasificacion
        assert (obj.valor_evaluado, obj.umbral_min_aplicado, obj.umbral_max_aplicado) == (
            Decimal(valor), Decimal("10"), Decimal("30"))


def test_evento_sin_umbrales_se_sigue_aceptando(monkeypatch):
    entidad, resultado = _ejecutar(monkeypatch, _dto())
    assert (entidad.valor_evaluado, entidad.umbral_min_aplicado, entidad.umbral_max_aplicado) == (None, None, None)
    assert resultado.umbral_min_aplicado is None


def test_umbral_minimo_mayor_que_maximo_se_rechaza():
    with pytest.raises(PydanticValidationError, match="umbral_min_aplicado no puede ser mayor"):
        _dto(umbral_min_aplicado=Decimal("30"), umbral_max_aplicado=Decimal("10"))


def test_umbrales_iguales_son_validos():
    dto = _dto(umbral_min_aplicado=Decimal("10"), umbral_max_aplicado=Decimal("10"))
    assert dto.umbral_min_aplicado == dto.umbral_max_aplicado


def test_repositorio_persiste_valor_y_umbrales():
    db = Mock()
    agregados = []
    db.add.side_effect = agregados.append
    ahora = datetime.now(timezone.utc)
    SqlAlchemyEventoEdgeRepository(db).guardar(EventoEdgeComputing(
        id_dispositivo_iot=3, id_sensor=7, clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA",
        fecha_captura=ahora, fecha_procesamiento=ahora, origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[], valor_evaluado=Decimal("35"),
        umbral_min_aplicado=Decimal("10"), umbral_max_aplicado=Decimal("30")))
    orm, = agregados
    assert (orm.valor_evaluado, orm.umbral_min_aplicado, orm.umbral_max_aplicado) == (
        Decimal("35"), Decimal("10"), Decimal("30"))

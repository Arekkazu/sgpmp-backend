# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M03-161-G66 / INC-M03-179-G57F RF-57: contrato del evento externo y regla de umbral |
# | 2026-10-30 | Arekkazu | INC-M04-224-G66 RF-57: categoria_variable, tipo_evento y estado_conectividad |
"""RF-57: el POST valida el evento (Fase 2 / Entradas) y las alertas de umbral nombran su regla."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import (
    EventoAlertaExternoDTO,
    ProcesarEventoAlertaDTO,
)
from src.telemetry.infrastructure.repositories.alerta_repository import _reglas_activas


def _evento(**cambios):
    base = dict(
        device_id=339, sensor_id=525, serial='GW', tipo_variable='TEMPERATURA_AMBIENTAL', valor='31.0',
        unidad='°C', timestamp_evento=datetime.now(timezone.utc).isoformat(), estado_dato='LECTURA_VALIDA',
        severidad_edge='LEVE', origen_evento='EDGE', id_evento_edge_computing=1,
    )
    base.update(cambios)
    return base


def test_evento_coherente_se_acepta():
    assert EventoAlertaExternoDTO(**_evento()).tipo_variable == 'TEMPERATURA_AMBIENTAL'
    assert EventoAlertaExternoDTO(**_evento(tipo_variable='humedad_relativa', unidad='%'))


@pytest.mark.parametrize('cambios, mensaje', [
    (dict(timestamp_evento=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()), 'futuro'),
    (dict(id_evento_edge_computing=None), 'referenciar su origen'),
    (dict(unidad='%'), 'no corresponde'),
    (dict(tipo_variable='VARIABLE_INEXISTENTE'), 'catálogo'),
    # INC-M04-224-G66 (#859): antes se ignoraban y respondía 201.
    (dict(categoria_variable='OTRA'), 'categoria_variable debe ser'),
    (dict(tipo_evento='INVENTADO'), 'tipo_evento debe ser'),
    (dict(categoria_variable='ANIMAL'), 'no corresponde a TEMPERATURA_AMBIENTAL'),
    (dict(estado_conectividad='si'), 'estado_conectividad'),
    (dict(estado_conectividad=1), 'estado_conectividad'),
])
def test_evento_incoherente_se_rechaza(cambios, mensaje):
    with pytest.raises(ValidationError) as exc:
        EventoAlertaExternoDTO(**_evento(**cambios))
    assert mensaje in str(exc.value)


def test_campos_del_catalogo_validos_se_aceptan():
    dto = EventoAlertaExternoDTO(**_evento(categoria_variable='ambiental', tipo_evento='UMBRAL_EXCEDIDO',
                                           estado_conectividad=False))
    assert (dto.categoria_variable, dto.tipo_evento, dto.estado_conectividad) == ('AMBIENTAL', 'UMBRAL_EXCEDIDO', False)
    assert EventoAlertaExternoDTO(**_evento(tipo_variable='PH_AGUA', unidad='pH', categoria_variable='HIDRICA'))


def test_los_flujos_internos_no_cambian_de_contrato():
    # RF-17 → RF-57 arma el DTO base con la unidad de la lectura; no se le exige el catálogo.
    assert ProcesarEventoAlertaDTO(**_evento(unidad='%', id_evento_edge_computing=None))


def _orm(reglas, meta):
    return SimpleNamespace(reglas_activas=reglas, metadato_evento=meta, tipo_variable='TEMPERATURA_AMBIENTAL')


def test_alerta_de_umbral_antigua_expone_la_regla_desde_el_metadato():
    reglas = _reglas_activas(_orm([], {'id_umbral_ambiental': 72, 'estado_semaforo': 'ROJO', 'version_umbral': 'v'}))
    assert reglas == [{'id': 72, 'nombre': 'UMBRAL_TEMPERATURA_AMBIENTAL_ROJO', 'tipo': 'UMBRAL_AMBIENTAL',
                       'id_umbral_ambiental': 72, 'version_umbral': 'v'}]


def test_reglas_guardadas_y_alertas_sin_umbral_no_se_tocan():
    assert _reglas_activas(_orm(['FRECUENCIA_CARDIACA_MODERADA'], {'id_umbral_ambiental': 1})) == ['FRECUENCIA_CARDIACA_MODERADA']
    assert _reglas_activas(_orm([], None)) == []

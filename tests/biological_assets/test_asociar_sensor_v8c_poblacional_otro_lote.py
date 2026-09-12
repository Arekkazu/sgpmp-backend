"""RF-49 Restriccion 4 (INC-M02-64-G88): un sensor POBLACIONAL solo puede
estar activo en un unico lote a la vez. V8b solo validaba por activo (que el
lote no tuviera ya otro sensor); faltaba V8c, la simetrica por sensor.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, AsociacionSensorActivo
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError


class ActivoRepoFake:
    def __init__(self, activo) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int):
        return self.activo


class SensorPortFake:
    def __init__(self, sensor) -> None:
        self.sensor = sensor

    def obtener_sensor_con_contexto(self, _id: int):
        return self.sensor


class InfraPortFake:
    def __init__(self, infra) -> None:
        self.infra = infra

    def obtener_activa(self, _id: int):
        return self.infra


class AsociacionRepoFake:
    def __init__(self, activas_por_sensor: list[AsociacionSensorActivo]) -> None:
        self.activas_por_sensor = activas_por_sensor

    def listar_activas_por_sensor(self, sensor_id: int, tipo_asociacion=None):
        return self.activas_por_sensor

    def listar_activas_por_activo(self, id_activo_biologico: int, tipo_asociacion=None):
        return []

    def obtener_activa_por_sensor_y_activo(self, sensor_id: int, id_activo_biologico: int):
        return None


def _use_case(activas_por_sensor):
    activo = ActivoBiologico(
        id_especie=40, tipo='POBLACIONAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=53,
    )
    sensor = SensorConsulta(
        id_sensor=1, nombre='Sensor 1', es_activo=True, id_dispositivo_iot=1,
        dispositivo_es_activo=True, id_infraestructura_dispositivo=1,
        id_infraestructura_area=1,
    )
    infra = InfraestructuraConsulta(
        id_infraestructura=1, nombre='Lote', tipo='Corral', es_activo=True, id_finca=10,
    )
    return AsociarSensorActivoUseCase(
        db=None,
        repo=AsociacionRepoFake(activas_por_sensor),
        activo_repo=ActivoRepoFake(activo),
        sensor_port=SensorPortFake(sensor),
        infra_port=InfraPortFake(infra),
    )


def _dto():
    return AsociarSensorActivoDTO(
        tipo_activo='LOTE', tipo_asociacion='POBLACIONAL',
        dispositivo_iot_id=1, sensor_id=1, id_infraestructura=1,
    )


def test_rechaza_sensor_poblacional_ya_activo_en_otro_lote():
    conflicto = AsociacionSensorActivo(
        id_activo_biologico=20, tipo_activo='LOTE', tipo_asociacion='poblacional',
        dispositivo_iot_id=1, sensor_id=1, id_infraestructura=1, id_usuario=1,
        fecha_inicio=datetime.now(timezone.utc), estado_asociacion='ACTIVA',
        id_asociacion_activo_sensor=105,
    )
    uc = _use_case([conflicto])

    with pytest.raises(ConflictError) as exc:
        uc.execute(53, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'SENSOR_YA_ASOCIADO_A_OTRO_LOTE'


def test_permite_si_la_unica_activa_es_del_mismo_activo():
    misma = AsociacionSensorActivo(
        id_activo_biologico=53, tipo_activo='LOTE', tipo_asociacion='poblacional',
        dispositivo_iot_id=1, sensor_id=1, id_infraestructura=1, id_usuario=1,
        fecha_inicio=datetime.now(timezone.utc), estado_asociacion='ACTIVA',
        id_asociacion_activo_sensor=105,
    )
    uc = _use_case([misma])

    # Pasa V8b/V8c; se detiene mas adelante por falta de db real (no es el foco del test).
    with pytest.raises(AttributeError):
        uc.execute(53, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

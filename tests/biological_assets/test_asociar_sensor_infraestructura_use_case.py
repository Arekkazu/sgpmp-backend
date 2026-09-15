"""RF-49 Tipo B (INC-M02-66-G90/#217): "Asociación Ambiental Compartida" --
un sensor ambiental se asocia a una infraestructura productiva completa
(no a un activo puntual) y aplica automáticamente a todos los activos que
residan en ella. Antes de este fix el único endpoint disponible exigía un
activo en el path y siempre persistía `id_activo_biologico` con ese valor.

`AsociarSensorInfraestructuraUseCase` persiste una única fila con
`id_activo_biologico = NULL` (la columna ya lo permitía en el esquema).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.gestion.asociar_sensor_infraestructura_use_case import (
    AsociarSensorInfraestructuraUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsulta
from src.biological_assets.infrastructure.dto.asociar_sensor_infraestructura_dto import (
    AsociarSensorInfraestructuraDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class SensorPortFake:
    def __init__(self, sensor: Optional[SensorConsulta]) -> None:
        self.sensor = sensor

    def obtener_sensor_con_contexto(self, _id: int):
        return self.sensor


class InfraPortFake:
    def __init__(self, infras: dict[int, InfraestructuraConsulta]) -> None:
        self.infras = infras

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)


class AsociacionRepoFake:
    def __init__(self, existente: Optional[AsociacionSensorActivo] = None) -> None:
        self.existente = existente
        self.guardado: Optional[AsociacionSensorActivo] = None
        self.auditorias: list[dict] = []

    def obtener_activa_por_sensor_e_infraestructura(self, sensor_id: int, id_infraestructura: int):
        return self.existente

    def guardar(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        entidad.id_asociacion_activo_sensor = 501
        self.guardado = entidad
        return entidad

    def registrar_auditoria(self, **kwargs) -> None:
        self.auditorias.append(kwargs)


def _sensor(**overrides) -> SensorConsulta:
    base = dict(
        id_sensor=9, nombre='Sensor ambiental', es_activo=True, id_dispositivo_iot=1,
        dispositivo_es_activo=True, id_infraestructura_dispositivo=1, id_infraestructura_area=2,
    )
    base.update(overrides)
    return SensorConsulta(**base)


def _infra(id_infraestructura: int, id_finca: int, **overrides) -> InfraestructuraConsulta:
    base = dict(
        id_infraestructura=id_infraestructura, nombre=f'Infra {id_infraestructura}',
        tipo='Estanque', es_activo=True, id_finca=id_finca,
    )
    base.update(overrides)
    return InfraestructuraConsulta(**base)


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def _dto(**overrides) -> AsociarSensorInfraestructuraDTO:
    base = dict(dispositivo_iot_id=1, sensor_id=9)
    base.update(overrides)
    return AsociarSensorInfraestructuraDTO(**base)


def _uc(sensor, infras, existente=None, asociacion_repo=None):
    return AsociarSensorInfraestructuraUseCase(
        db=DbFake(),
        repo=asociacion_repo or AsociacionRepoFake(existente),
        sensor_port=SensorPortFake(sensor),
        infra_port=InfraPortFake(infras),
    )


def test_infraestructura_inexistente_o_inactiva_es_422():
    uc = _uc(_sensor(), infras={})  # id_infraestructura=1 no está en el dict

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'INFRAESTRUCTURA_NO_ENCONTRADA'


def test_sensor_inexistente_es_404():
    uc = _uc(None, infras={1: _infra(1, id_finca=10)})

    with pytest.raises(NotFoundError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'SENSOR_NO_ENCONTRADO'


def test_sensor_inactivo_es_422():
    uc = _uc(_sensor(es_activo=False), infras={1: _infra(1, id_finca=10)})

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'SENSOR_INACTIVO'


def test_dispositivo_inactivo_es_422():
    uc = _uc(_sensor(dispositivo_es_activo=False), infras={1: _infra(1, id_finca=10)})

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'DISPOSITIVO_INACTIVO'


def test_sensor_sin_area_es_422():
    uc = _uc(_sensor(id_infraestructura_area=None), infras={1: _infra(1, id_finca=10)})

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'SENSOR_SIN_AREA'


def test_finca_incompatible_es_409():
    # Sensor instalado en infra 2 (finca 20); se intenta asociar a infra 1 (finca 10).
    uc = _uc(
        _sensor(id_infraestructura_area=2),
        infras={1: _infra(1, id_finca=10), 2: _infra(2, id_finca=20)},
    )

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'INFRAESTRUCTURA_INCOMPATIBLE'


def test_asociacion_ambiental_duplicada_es_409():
    existente = AsociacionSensorActivo(
        id_activo_biologico=None, tipo_activo=None, tipo_asociacion='ambiental',
        dispositivo_iot_id=1, sensor_id=9, id_infraestructura=1, id_usuario=1,
        fecha_inicio=datetime.now(timezone.utc), estado_asociacion='ACTIVA',
        id_asociacion_activo_sensor=99,
    )
    uc = _uc(
        _sensor(id_infraestructura_area=1),
        infras={1: _infra(1, id_finca=10)},
        existente=existente,
    )

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, _dto(), _usuario())

    assert exc.value.code == 'ASOCIACION_AMBIENTAL_YA_EXISTE'


def test_creacion_exitosa_persiste_con_id_activo_biologico_null():
    repo = AsociacionRepoFake(existente=None)
    uc = _uc(_sensor(id_infraestructura_area=1), infras={1: _infra(1, id_finca=10)}, asociacion_repo=repo)

    resultado = uc.execute(1, _dto(motivo='Monitoreo de estanque completo'), _usuario())

    assert resultado.id_asociacion_activo_sensor == 501
    assert resultado.id_activo_biologico is None
    assert resultado.tipo_activo is None
    assert resultado.tipo_asociacion == 'ambiental'
    assert resultado.id_infraestructura == 1
    assert resultado.estado_asociacion == 'ACTIVA'
    assert repo.guardado is resultado
    assert len(repo.auditorias) == 1
    assert repo.auditorias[0]['tipo_op'] == 'CREATE'

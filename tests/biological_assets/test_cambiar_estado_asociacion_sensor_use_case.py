"""RF-49 (INC-M02-65-G89): no existia ningun endpoint para gestionar el ciclo
de vida (ACTIVA/INACTIVA) de una asociacion sensor-activo -- las 3 transiciones
formales del RF-49 devolvian 404 al no existir el endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.cambiar_estado_asociacion_sensor_use_case import (
    CambiarEstadoAsociacionSensorUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo
from src.biological_assets.infrastructure.dto.cambiar_estado_asociacion_sensor_dto import (
    CambiarEstadoAsociacionSensorDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class RepoFake:
    def __init__(self, asociacion: AsociacionSensorActivo) -> None:
        self.asociacion = asociacion
        self.auditorias: list[dict] = []

    def obtener_por_id(self, id_asociacion: int):
        return self.asociacion if id_asociacion == self.asociacion.id_asociacion_activo_sensor else None

    def actualizar_estado(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        self.asociacion = entidad
        return entidad

    def registrar_auditoria(self, **kwargs) -> None:
        self.auditorias.append(kwargs)


class DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _asociacion(estado: str, id_activo: int = 1, id_asociacion: int = 10):
    return AsociacionSensorActivo(
        id_activo_biologico=id_activo, tipo_activo='INDIVIDUAL', tipo_asociacion='directa',
        dispositivo_iot_id=1, sensor_id=1, id_infraestructura=1, id_usuario=1,
        fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        estado_asociacion=estado, id_asociacion_activo_sensor=id_asociacion,
    )


def _usuario():
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def test_desactiva_asociacion_activa():
    repo = RepoFake(_asociacion('ACTIVA'))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    resultado = uc.execute(1, 10, CambiarEstadoAsociacionSensorDTO(estado_nuevo='INACTIVA'), _usuario())

    assert resultado.estado_asociacion == 'INACTIVA'
    assert resultado.fecha_fin is not None


def test_reactiva_asociacion_inactiva():
    repo = RepoFake(_asociacion('INACTIVA'))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    resultado = uc.execute(1, 10, CambiarEstadoAsociacionSensorDTO(estado_nuevo='ACTIVA'), _usuario())

    assert resultado.estado_asociacion == 'ACTIVA'
    assert resultado.fecha_fin is None


def test_rechaza_transicion_a_superada():
    repo = RepoFake(_asociacion('INACTIVA'))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(1, 10, CambiarEstadoAsociacionSensorDTO(estado_nuevo='SUPERADA'), _usuario())

    assert exc.value.code == 'TRANSICION_INVALIDA'


def test_rechaza_estado_redundante():
    repo = RepoFake(_asociacion('ACTIVA'))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, 10, CambiarEstadoAsociacionSensorDTO(estado_nuevo='ACTIVA'), _usuario())

    assert exc.value.code == 'ESTADO_REDUNDANTE'


def test_404_si_no_existe():
    repo = RepoFake(_asociacion('ACTIVA'))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    with pytest.raises(NotFoundError):
        uc.execute(1, 999, CambiarEstadoAsociacionSensorDTO(estado_nuevo='INACTIVA'), _usuario())


def test_404_si_asociacion_es_de_otro_activo():
    repo = RepoFake(_asociacion('ACTIVA', id_activo=1, id_asociacion=10))
    uc = CambiarEstadoAsociacionSensorUseCase(db=DbFake(), repo=repo)

    with pytest.raises(NotFoundError):
        uc.execute(2, 10, CambiarEstadoAsociacionSensorDTO(estado_nuevo='INACTIVA'), _usuario())

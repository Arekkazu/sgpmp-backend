"""RF-48 (INC-M02-89-G83/TC-M02-308): E-05 (INFRAESTRUCTURA_DESTINO_INVALIDA)
devolvía el mismo mensaje genérico ("no existe o no está activa") tanto para
una infraestructura destino inexistente como para una existente pero inactiva.
Mejora de usabilidad (no defecto funcional, según el propio reporte de QA):
distinguir el motivo real en el mensaje. El `error_code` y el status HTTP no
cambian.
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistorialInfraestructura
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class ActivoRepoFake:
    def __init__(self, activo, asociacion) -> None:
        self.activo = activo
        self.asociacion = asociacion

    def obtener_por_id(self, _id: int):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return self.asociacion


class TransferenciaRepoFake:
    def hay_transferencia_en_progreso(self, _id: int) -> bool:
        return False


class InfraPortFake:
    """`existentes` simula infraestructuras que existen pero pueden estar
    inactivas (no aparecen en `activas`); las que no están en ninguno de los
    dos conjuntos no existen en absoluto."""

    def __init__(self, activas: dict[int, InfraestructuraConsulta], existentes: set[int]) -> None:
        self.activas = activas
        self.existentes = existentes

    def obtener_activa(self, id_infraestructura: int):
        return self.activas.get(id_infraestructura)

    def existe(self, id_infraestructura: int) -> bool:
        return id_infraestructura in self.existentes or id_infraestructura in self.activas


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=48, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=279, identificador='QAJE-TRF-279',
    )


def _asociacion() -> HistorialInfraestructura:
    return HistorialInfraestructura(
        id_historial=1, id_activo_biologico=279, id_infraestructura=48,
        nombre_infraestructura='Infra 48', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )


def _dto(destino: int) -> RegistrarTransferenciaDTO:
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=48, infraestructura_destino_id=destino,
        fecha_transferencia='2026-01-01', motivo_transferencia='prueba',
    )


def test_destino_inexistente_dice_no_existe():
    """TC-M02-308-A: infraestructura destino 99999 nunca existió."""
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(_activo(), _asociacion()),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake(activas={}, existentes=set()),
        parametros_port=None,
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(279, _dto(destino=99999), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'INFRAESTRUCTURA_DESTINO_INVALIDA'
    assert exc.value.message == 'La infraestructura con id 99999 no existe.'


def test_destino_inactivo_dice_se_encuentra_inactiva():
    """TC-M02-308-B: infraestructura destino 50 existe pero es_activo=False."""
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(_activo(), _asociacion()),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake(activas={}, existentes={50}),
        parametros_port=None,
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(279, _dto(destino=50), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'INFRAESTRUCTURA_DESTINO_INVALIDA'
    assert exc.value.message == 'La infraestructura con id 50 se encuentra inactiva.'

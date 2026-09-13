"""RF-49 CU11 Flujo Alterno "Activo Biologico No Valido" (INC-M02-63-G88):
inexistente y BAJA comparten el mismo flujo y deben responder 422
(BusinessRuleError), no 404. V2 (BAJA) ya lo hacia bien; V1 (inexistente)
usaba NotFoundError -- inconsistente con su propio vecino en el mismo metodo.
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class ActivoRepoFake:
    def __init__(self, activo) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int):
        return self.activo


def _use_case(activo):
    return AsociarSensorActivoUseCase(
        db=None, repo=None, activo_repo=ActivoRepoFake(activo),
        sensor_port=None, infra_port=None,
    )


def _dto():
    return AsociarSensorActivoDTO(
        tipo_activo='LOTE', tipo_asociacion='POBLACIONAL',
        dispositivo_iot_id=1, sensor_id=1, id_infraestructura=1,
    )


def test_activo_inexistente_responde_422_no_404():
    uc = _use_case(None)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(99999, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_activo_en_baja_responde_422():
    activo = ActivoBiologico(
        id_especie=40, tipo='POBLACIONAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=EstadoActivo.BAJA, id_usuario=1,
        id_activo_biologico=53,
    )
    uc = _use_case(activo)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(53, _dto(), UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'ACTIVO_EN_BAJA'

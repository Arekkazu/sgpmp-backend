"""RF-48 (INC-M02-73-G80/TC-M02-134): E-06 (DESTINO_IGUAL_ORIGEN) usaba
ValidationError (HTTP 400), pero el contrato del endpoint no declara 400 y
espera 422 -- misma familia de regla de negocio que C1/C3 (BusinessRuleError).
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
from src.shared.errors import BusinessRuleError, ValidationError


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
    def __init__(self, infras: dict[int, InfraestructuraConsulta]) -> None:
        self.infras = infras

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)

    def calcular_ocupacion(self, _id: int) -> int:
        return 0


def test_destino_igual_origen_es_422_no_400():
    activo = ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=51, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=294, identificador='QAJE-TRF-REGLAS',
    )
    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=294, id_infraestructura=51,
        nombre_infraestructura='Corral QA JE Destino OK', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    infra_51 = InfraestructuraConsulta(
        id_infraestructura=51, nombre='Corral QA JE Destino OK', tipo='Corral',
        es_activo=True, id_finca=10,
    )
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo, asociacion),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({51: infra_51}),
    )
    dto = RegistrarTransferenciaDTO(
        infraestructura_origen_id=51, infraestructura_destino_id=51,
        fecha_transferencia='2026-01-01', motivo_transferencia='prueba',
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(294, dto, usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'DESTINO_IGUAL_ORIGEN'
    assert exc.value.status_code == 422
    assert not isinstance(exc.value, ValidationError)

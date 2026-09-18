"""RF-48 (INC-M02-88-G83/TC-M02-G83, hallazgo DEF-G83-01): E-04
(SIN_INFRAESTRUCTURA_ORIGEN) y E-05 (INFRAESTRUCTURA_DESTINO_INVALIDA) usaban
ValidationError (HTTP 400), pero el contrato del endpoint (OpenAPI) no declara
400 y espera 422 -- misma familia de regla de negocio que ya corrigió
INC-M02-73-G80 para DESTINO_IGUAL_ORIGEN (BusinessRuleError).

Casos QA reproducidos:
- TC-M02-307: activo ACTIVO sin infraestructura origen vigente (E-04).
- TC-M02-308-A: infraestructura destino inexistente (E-05).
- TC-M02-308-B: infraestructura destino existente pero inactiva (E-05).
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
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

    def existe(self, id_infraestructura: int) -> bool:
        return id_infraestructura in self.infras

    def calcular_ocupacion(self, _id: int) -> int:
        return 0

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        return True


def _activo(id_activo: int, id_infraestructura: int = 48) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=id_infraestructura, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=id_activo, identificador=f'QAJE-TRF-{id_activo}',
    )


def _dto(destino: int, origen: int = 48) -> RegistrarTransferenciaDTO:
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=origen, infraestructura_destino_id=destino,
        fecha_transferencia='2026-01-01', motivo_transferencia='prueba',
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def test_sin_infraestructura_origen_es_422_no_400():
    """TC-M02-307: activo ACTIVO sin ninguna asociación vigente en el historial."""
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(_activo(287), asociacion=None),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({}),
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(287, _dto(destino=50), _usuario())

    assert exc.value.code == 'SIN_INFRAESTRUCTURA_ORIGEN'
    assert exc.value.status_code == 422
    assert not isinstance(exc.value, ValidationError)


def test_infraestructura_destino_inexistente_es_422_no_400():
    """TC-M02-308-A: infraestructura destino 99999 no existe."""
    from src.biological_assets.domain.entities.activo_biologico import HistorialInfraestructura

    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=279, id_infraestructura=48,
        nombre_infraestructura='Infra 48', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(_activo(279), asociacion),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({}),  # 99999 no está en el dict -> None
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(279, _dto(destino=99999), _usuario())

    assert exc.value.code == 'INFRAESTRUCTURA_DESTINO_INVALIDA'
    assert exc.value.status_code == 422
    assert not isinstance(exc.value, ValidationError)


def test_infraestructura_destino_inactiva_es_422_no_400():
    """TC-M02-308-B: infraestructura destino 50 existe pero es_activo=False --
    obtener_activa() ya la modela como None (no distingue inexistente de inactiva)."""
    from src.biological_assets.domain.entities.activo_biologico import HistorialInfraestructura

    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=279, id_infraestructura=48,
        nombre_infraestructura='Infra 48', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    uc = RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(_activo(279), asociacion),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({}),  # inactiva -> obtener_activa() retorna None
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(279, _dto(destino=50), _usuario())

    assert exc.value.code == 'INFRAESTRUCTURA_DESTINO_INVALIDA'
    assert exc.value.status_code == 422
    assert not isinstance(exc.value, ValidationError)

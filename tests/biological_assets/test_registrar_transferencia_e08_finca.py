"""RF-48 (INC-M02-74-G80): execute() nunca validaba alcance por finca entre
infraestructura origen y destino -- listar_infraestructuras_disponibles ya
lo filtraba para el listado, pero un POST directo con un
infraestructura_destino_id de otra finca no era rechazado (E-08 ausente).
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
    def __init__(self, infras: dict[int, InfraestructuraConsulta]) -> None:
        self.infras = infras

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)

    def calcular_ocupacion(self, _id: int) -> int:
        return 0

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        return True


def _infra(id_infraestructura, id_finca):
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura, nombre=f'Infra {id_infraestructura}',
        tipo='Corral', es_activo=True, id_finca=id_finca,
    )


def _use_case(infras: dict[int, InfraestructuraConsulta]):
    activo = ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=99, identificador='A-1',
    )
    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=99, id_infraestructura=1,
        nombre_infraestructura='Infra 1', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    return RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo, asociacion),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake(infras),
    )


def _dto():
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=1, infraestructura_destino_id=2,
        fecha_transferencia='2026-01-01', motivo_transferencia='prueba',
    )


def test_rechaza_destino_de_otra_finca():
    uc = _use_case({1: _infra(1, id_finca=10), 2: _infra(2, id_finca=20)})

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(99, _dto(), usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'DESTINO_OTRA_FINCA'


def test_permite_destino_de_la_misma_finca():
    uc = _use_case({1: _infra(1, id_finca=10), 2: _infra(2, id_finca=10)})

    # Pasa E-08; se detiene mas adelante por falta de db real (no es el foco del test).
    with pytest.raises(AttributeError):
        uc.execute(99, _dto(), usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

"""RF-48 (INC-M02-72-G80): no existia ningun modelo de compatibilidad entre
tipo de infraestructura y especie del activo (C2) -- un bovino se aceptaba en
un Estanque. Cubre execute() (E-07b) y el filtro del listado.
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

ID_ESPECIE_BOVINO = 11  # 'Miguel' en el seed local: "Ganado vacuno para produccion de leche y carne"
ID_ESPECIE_TILAPIA = 10


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
    """Compatibilidad C2 explicita por caso: solo 'Estanque' esta restringido a un set de especies."""

    def __init__(self, infras: dict[int, InfraestructuraConsulta], especies_compatibles_estanque: set[int]) -> None:
        self.infras = infras
        self.especies_compatibles_estanque = especies_compatibles_estanque

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)

    def listar_activas(self, excluir_id=None):
        return [i for i in self.infras.values() if i.id_infraestructura != excluir_id]

    def calcular_ocupacion(self, _id: int) -> int:
        return 0

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        if tipo_infraestructura != 'Estanque':
            return True  # sin regla configurada -> sin restriccion, igual que en produccion
        return id_especie in self.especies_compatibles_estanque


def _infra(id_infraestructura, tipo, id_finca=10):
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura, nombre=f'Infra {id_infraestructura}',
        tipo=tipo, es_activo=True, id_finca=id_finca,
    )


def _use_case(infra_port, id_especie):
    activo = ActivoBiologico(
        id_especie=id_especie, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=99, identificador='A-1',
    )
    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=99, id_infraestructura=1,
        nombre_infraestructura='Infra 1', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    return RegistrarTransferenciaUseCase(
        db=None, activo_repo=ActivoRepoFake(activo, asociacion),
        transferencia_repo=TransferenciaRepoFake(), infra_port=infra_port,
    )


def _dto(destino):
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=1, infraestructura_destino_id=destino,
        fecha_transferencia='2026-01-01', motivo_transferencia='prueba',
    )


def test_rechaza_bovino_hacia_estanque():
    infras = {1: _infra(1, 'Corral'), 2: _infra(2, 'Estanque')}
    uc = _use_case(InfraPortFake(infras, {ID_ESPECIE_TILAPIA}), ID_ESPECIE_BOVINO)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(99, _dto(2), usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))

    assert exc.value.code == 'INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA'


def test_permite_pez_hacia_estanque_compatible():
    infras = {1: _infra(1, 'Corral'), 2: _infra(2, 'Estanque')}
    uc = _use_case(InfraPortFake(infras, {ID_ESPECIE_TILAPIA}), ID_ESPECIE_TILAPIA)

    # Pasa E-07b; se detiene mas adelante por falta de db real (no es el foco del test).
    with pytest.raises(AttributeError):
        uc.execute(99, _dto(2), usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))


def test_listado_excluye_estanque_incompatible_para_bovino():
    infras = {1: _infra(1, 'Corral'), 2: _infra(2, 'Estanque'), 3: _infra(3, 'Corral')}
    uc = _use_case(InfraPortFake(infras, {ID_ESPECIE_TILAPIA}), ID_ESPECIE_BOVINO)

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [3]

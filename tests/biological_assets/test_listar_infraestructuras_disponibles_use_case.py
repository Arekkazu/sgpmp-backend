"""RF-48 (INC-M02-74-G80): 'disponibles' debia excluir solo la infraestructura
origen, sin aplicar compatibilidad de especie (C1), capacidad (C3) ni alcance
por finca -- el usuario podia elegir un destino que el POST luego rechazaba.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, DetallePoblacional
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int):
        return self.activo


class InfraPortFake:
    def __init__(self, origen: InfraestructuraConsulta, candidatas: list[InfraestructuraConsulta], ocupaciones: dict[int, int]) -> None:
        self.origen = origen
        self.candidatas = candidatas
        self.ocupaciones = ocupaciones

    def obtener_activa(self, id_infraestructura: int):
        return self.origen if id_infraestructura == self.origen.id_infraestructura else None

    def listar_activas(self, excluir_id=None):
        return [i for i in self.candidatas if i.id_infraestructura != excluir_id]

    def calcular_ocupacion(self, id_infraestructura: int) -> int:
        return self.ocupaciones.get(id_infraestructura, 0)

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        return True


def _infra(id_infraestructura, id_finca, id_especie=None, capacidad_maxima=None):
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura,
        nombre=f'Infra {id_infraestructura}',
        tipo='Corral',
        es_activo=True,
        id_finca=id_finca,
        capacidad_maxima=capacidad_maxima,
        id_especie=id_especie,
    )


def _activo_individual(id_especie=40, id_infraestructura=1):
    return ActivoBiologico(
        id_especie=id_especie,
        tipo='INDIVIDUAL',
        origen_financiero='PROPIO',
        id_infraestructura=id_infraestructura,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=99,
    )


def _use_case(activo_repo, infra_port):
    return RegistrarTransferenciaUseCase(
        db=None,
        activo_repo=activo_repo,
        transferencia_repo=None,
        infra_port=infra_port,
    )


def test_excluye_infraestructura_de_otra_finca():
    activo = _activo_individual()
    origen = _infra(1, id_finca=10)
    otra_finca = _infra(2, id_finca=20)
    misma_finca = _infra(3, id_finca=10)
    uc = _use_case(ActivoRepoFake(activo), InfraPortFake(origen, [otra_finca, misma_finca], {}))

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [3]


def test_excluye_infraestructura_de_especie_incompatible():
    activo = _activo_individual(id_especie=40)
    origen = _infra(1, id_finca=10)
    especie_distinta = _infra(2, id_finca=10, id_especie=41)
    especie_igual = _infra(3, id_finca=10, id_especie=40)
    sin_restriccion = _infra(4, id_finca=10, id_especie=None)
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(origen, [especie_distinta, especie_igual, sin_restriccion], {}),
    )

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert {i['id_infraestructura'] for i in resultado} == {3, 4}


def test_excluye_infraestructura_sin_capacidad_disponible():
    activo = ActivoBiologico(
        id_especie=40, tipo='POBLACIONAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=1, id_usuario=1, id_activo_biologico=296,
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=10, cantidad_actual=10, peso_promedio_inicial=Decimal('20'),
        ),
    )
    origen = _infra(1, id_finca=10)
    llena = _infra(2, id_finca=10, capacidad_maxima=50)
    con_cupo = _infra(3, id_finca=10, capacidad_maxima=50)
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(origen, [llena, con_cupo], {2: 48, 3: 30}),
    )

    resultado = uc.listar_infraestructuras_disponibles(296, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [3]


def test_sin_origen_activo_no_filtra_por_finca():
    """Si la infraestructura origen ya no esta activa (caso borde), no se puede
    determinar el alcance por finca -- se degrada a no filtrar por finca en vez
    de ocultar todo el listado."""
    activo = _activo_individual()
    origen_inactiva = _infra(1, id_finca=10)
    otra_finca = _infra(2, id_finca=99)
    uc = _use_case(ActivoRepoFake(activo), InfraPortFake(origen_inactiva, [otra_finca], {}))
    uc.infra_port.obtener_activa = lambda _id: None  # origen ya no activo

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [2]

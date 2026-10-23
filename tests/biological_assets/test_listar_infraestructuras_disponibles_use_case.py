# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: el doble del área declara sus especies (RFC-012) |
# | 2026-10-23 | destroyerban | DEV-23 RF-33/34/36/48: capacidad efectiva del área (RFC-012) |
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
from src.configuration.domain.services.capacidad_area import EspecieDelArea


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int):
        return self.activo


class InfraPortFake:
    def __init__(
        self,
        origen: InfraestructuraConsulta,
        candidatas: list[InfraestructuraConsulta],
        ocupaciones: dict[int, int],
        densidad_activo: Decimal | None = Decimal('1'),
    ) -> None:
        self.origen = origen
        self.candidatas = candidatas
        self.ocupaciones = ocupaciones
        self.densidad_activo = densidad_activo

    def obtener_especie(self, id_especie: int):
        # Especie del activo: grupo G y densidad configurable (RFC-012, DEV-23).
        return EspecieDelArea(id_especie, 'Activo', 'G', self.densidad_activo)

    def obtener_activa(self, id_infraestructura: int):
        return self.origen if id_infraestructura == self.origen.id_infraestructura else None

    def listar_activas(self, excluir_id=None):
        return [i for i in self.candidatas if i.id_infraestructura != excluir_id]

    def calcular_ocupacion(self, id_infraestructura: int) -> int:
        return self.ocupaciones.get(id_infraestructura, 0)

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        return True


def _infra(id_infraestructura, id_finca, id_especie=None, grupo='G', densidad=Decimal('1'), superficie=Decimal('100')):
    especies = [EspecieDelArea(id_especie, 'E', grupo, densidad)] if id_especie is not None else []
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura,
        nombre=f'Infra {id_infraestructura}',
        tipo='Corral',
        es_activo=True,
        id_finca=id_finca,
        superficie=superficie,
        capacidad_maxima=int(densidad * superficie) if especies and densidad is not None else None,
        especies=especies,
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
        parametros_port=None,
    )


def test_excluye_infraestructura_de_otra_finca():
    activo = _activo_individual()
    origen = _infra(1, id_finca=10)
    otra_finca = _infra(2, id_finca=20)
    misma_finca = _infra(3, id_finca=10)
    uc = _use_case(ActivoRepoFake(activo), InfraPortFake(origen, [otra_finca, misma_finca], {}))

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [3]


def test_excluye_infraestructura_de_otro_grupo_de_manejo():
    # RFC-012 (DEV-23): el destino puede alojar otra especie si es del mismo grupo.
    activo = _activo_individual(id_especie=40)
    origen = _infra(1, id_finca=10)
    otro_grupo = _infra(2, id_finca=10, id_especie=41, grupo='OTRO')
    especie_igual = _infra(3, id_finca=10, id_especie=40)
    sin_especies = _infra(4, id_finca=10, id_especie=None)
    otra_especie_mismo_grupo = _infra(5, id_finca=10, id_especie=42)
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(origen, [otro_grupo, especie_igual, sin_especies, otra_especie_mismo_grupo], {}),
    )

    resultado = uc.listar_infraestructuras_disponibles(99, usuario=None)

    assert {i['id_infraestructura'] for i in resultado} == {3, 4, 5}


def test_excluye_infraestructura_sin_capacidad_disponible():
    activo = ActivoBiologico(
        id_especie=40, tipo='POBLACIONAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=1, id_usuario=1, id_activo_biologico=296,
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=10, cantidad_actual=10, peso_promedio_inicial=Decimal('20'),
        ),
    )
    origen = _infra(1, id_finca=10)
    # capacidad = floor(1 ind/m² × 50 m²) = 50: 48 + 10 no cabe, 30 + 10 sí.
    llena = _infra(2, id_finca=10, id_especie=40, superficie=Decimal('50'))
    con_cupo = _infra(3, id_finca=10, id_especie=40, superficie=Decimal('50'))
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(origen, [llena, con_cupo], {2: 48, 3: 30}),
    )

    resultado = uc.listar_infraestructuras_disponibles(296, usuario=None)

    assert [i['id_infraestructura'] for i in resultado] == [3]
    assert resultado[0]['ocupacion_actual'] == 30
    assert resultado[0]['capacidad_maxima'] == 50


def test_excluye_destino_si_el_entrante_baja_el_minimo_y_no_cabe():
    # H-12.3: el destino (densidad 1, 50 m², 30 alojados) tiene cupo 50, pero con un
    # entrante de densidad 0.5 la capacidad baja a floor(0.5 × 50) = 25 < 30 + 10.
    activo = ActivoBiologico(
        id_especie=41, tipo='POBLACIONAL', origen_financiero='PROPIO',
        id_infraestructura=1, id_estado=1, id_usuario=1, id_activo_biologico=297,
        detalle_poblacional=DetallePoblacional(cantidad_inicial=10, cantidad_actual=10),
    )
    destino = _infra(2, id_finca=10, id_especie=40, superficie=Decimal('50'))
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(_infra(1, id_finca=10), [destino], {2: 30}, densidad_activo=Decimal('0.5')),
    )

    assert uc.listar_infraestructuras_disponibles(297, usuario=None) == []


def test_especie_sin_densidad_no_tiene_destinos():
    activo = _activo_individual(id_especie=40)
    uc = _use_case(
        ActivoRepoFake(activo),
        InfraPortFake(_infra(1, id_finca=10), [_infra(3, id_finca=10)], {}, densidad_activo=None),
    )

    assert uc.listar_infraestructuras_disponibles(99, usuario=None) == []


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

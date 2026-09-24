"""DEF-RF48-02 / INC-M02-40-G28 (RF-36 + RF-48): al transferir un lote
poblacional a una infraestructura con distinta superficie, `id_infraestructura`
y el historial se actualizaban correctamente, pero
`modulo2.detalles_activos_biologicos_poblacionales.densidad` quedaba
"congelada" con el valor calculado contra la superficie de origen -- nunca se
recalculaba contra la superficie de la infraestructura destino
(`densidad = cantidad_actual / superficie`, RF-36).

Caso reportado por QA (`TC-M02-202`): lote 130 (`cantidad_actual=5`),
transferido de Alevinera-01 (500 m², densidad 0.01) a Estanque-01 (2500 m²)
-- se esperaba densidad 0.002 y quedó en 0.01.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    HistorialInfraestructura,
    Transferencia,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.ejecutados: list[tuple[str, dict]] = []

    def execute(self, stmt, params: Optional[dict] = None):
        self.ejecutados.append((str(stmt), params or {}))

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico, asociacion: HistorialInfraestructura) -> None:
        self.activo = activo
        self.asociacion = asociacion

    def obtener_por_id(self, _id: int):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return self.asociacion


class TransferenciaRepoFake:
    def hay_transferencia_en_progreso(self, _id: int) -> bool:
        return False

    def guardar(self, transferencia: Transferencia) -> Transferencia:
        transferencia.id_movimiento = 1
        return transferencia


class InfraPortFake:
    def __init__(self, infras: dict[int, InfraestructuraConsulta]) -> None:
        self.infras = infras

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)

    def calcular_ocupacion(self, _id: int) -> int:
        return 0

    def es_tipo_compatible(self, _tipo_infraestructura: str, _id_especie: int) -> bool:
        return True


class ParametrosPortFake:
    def __init__(self, densidad_maxima: Decimal | None) -> None:
        self.densidad_maxima = densidad_maxima

    def obtener_densidad_maxima(self, _id_especie: int):
        return self.densidad_maxima


def _infra(id_infraestructura: int, id_finca: int, superficie: Optional[Decimal]) -> InfraestructuraConsulta:
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura, nombre=f'Infra {id_infraestructura}',
        tipo='Estanque', es_activo=True, id_finca=id_finca, superficie=superficie,
    )


def _activo_poblacional(cantidad_actual: int, id_infraestructura: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4, tipo='POBLACIONAL', origen_financiero='compra',
        id_infraestructura=id_infraestructura, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=130,
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=cantidad_actual, cantidad_actual=cantidad_actual,
            densidad=Decimal('0.01'),
        ),
    )


def _asociacion(id_infraestructura: int) -> HistorialInfraestructura:
    return HistorialInfraestructura(
        id_historial=1, id_activo_biologico=130, id_infraestructura=id_infraestructura,
        nombre_infraestructura=f'Infra {id_infraestructura}', tipo_infraestructura='Estanque',
        fecha_inicio=None, fecha_fin=None,
    )


def _dto(origen: int, destino: int) -> RegistrarTransferenciaDTO:
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=origen, infraestructura_destino_id=destino,
        fecha_transferencia=date(2026, 9, 8), motivo_transferencia='Transferencia válida a Estanque-01',
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def test_densidad_se_recalcula_contra_la_superficie_destino() -> None:
    """Caso TC-M02-202: 5 individuos, de 500 m² (0.01) a 2500 m² -> 0.002."""
    activo = _activo_poblacional(cantidad_actual=5, id_infraestructura=3)
    db = DbFake()
    uc = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo, _asociacion(3)),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            3: _infra(3, id_finca=1, superficie=Decimal('500')),
            1: _infra(1, id_finca=1, superficie=Decimal('2500')),
        }),
        parametros_port=ParametrosPortFake(Decimal('0.01')),
    )

    uc.execute(130, _dto(origen=3, destino=1), _usuario())

    assert activo.detalle_poblacional.densidad == Decimal('5') / Decimal('2500')
    actualizaciones_densidad = [
        params for _, params in db.ejecutados if 'densidad' in params
    ]
    assert len(actualizaciones_densidad) == 1
    assert actualizaciones_densidad[0] == {'id': 130, 'densidad': Decimal('5') / Decimal('2500')}
    assert db.commits == 1


def test_activo_individual_no_toca_detalle_poblacional() -> None:
    """Un activo INDIVIDUAL no tiene detalle_poblacional -- no debe intentar
    actualizar densidad."""
    activo = ActivoBiologico(
        id_especie=2, tipo='INDIVIDUAL', origen_financiero='compra',
        id_infraestructura=3, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=51, identificador='A-51',
    )
    db = DbFake()
    uc = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo, _asociacion(3)),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            3: _infra(3, id_finca=1, superficie=Decimal('500')),
            1: _infra(1, id_finca=1, superficie=Decimal('2500')),
        }),
        parametros_port=ParametrosPortFake(Decimal('0.01')),
    )

    uc.execute(51, _dto(origen=3, destino=1), _usuario())

    assert not [params for _, params in db.ejecutados if 'densidad' in params]


def test_destino_sin_superficie_configurada_rechaza_transferencia() -> None:
    """Sin superficie no se puede comprobar la restricción de densidad."""
    activo = _activo_poblacional(cantidad_actual=5, id_infraestructura=3)
    db = DbFake()
    uc = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo, _asociacion(3)),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            3: _infra(3, id_finca=1, superficie=Decimal('500')),
            1: _infra(1, id_finca=1, superficie=None),
        }),
        parametros_port=ParametrosPortFake(Decimal('0.01')),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(130, _dto(origen=3, destino=1), _usuario())

    assert exc_info.value.code == 'SUPERFICIE_INFRAESTRUCTURA_INVALIDA'
    assert activo.detalle_poblacional.densidad == Decimal('0.01')
    assert db.ejecutados == []


def test_transferencia_rechaza_densidad_superior_al_limite_de_especie() -> None:
    activo = _activo_poblacional(cantidad_actual=50, id_infraestructura=3)
    db = DbFake()
    uc = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo, _asociacion(3)),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            3: _infra(3, id_finca=1, superficie=Decimal('500')),
            1: _infra(1, id_finca=1, superficie=Decimal('100')),
        }),
        parametros_port=ParametrosPortFake(Decimal('0.2')),
    )

    with pytest.raises(ConflictError) as exc_info:
        uc.execute(130, _dto(origen=3, destino=1), _usuario())

    assert exc_info.value.code == 'DENSIDAD_MAXIMA_SUPERADA'
    assert db.ejecutados == []


def test_transferencia_sin_limite_de_especie_no_omite_validacion() -> None:
    activo = _activo_poblacional(cantidad_actual=5, id_infraestructura=3)
    db = DbFake()
    uc = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=ActivoRepoFake(activo, _asociacion(3)),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            3: _infra(3, id_finca=1, superficie=Decimal('500')),
            1: _infra(1, id_finca=1, superficie=Decimal('2500')),
        }),
        parametros_port=ParametrosPortFake(None),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(130, _dto(origen=3, destino=1), _usuario())

    assert exc_info.value.code == 'DENSIDAD_MAXIMA_NO_CONFIGURADA'
    assert db.ejecutados == []

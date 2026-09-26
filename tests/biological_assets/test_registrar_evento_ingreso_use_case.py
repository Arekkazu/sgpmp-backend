"""RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima, ingreso de
individuos"): no existía ningún mecanismo de alta de individuos a un lote --
solo el flujo de BAJA. `RegistrarEventoIngresoUseCase` es la contraparte,
mismo patrón estructural que `RegistrarEventoBajaUseCase` (RF-45), con una
validación adicional que RF-45 no necesita: la densidad resultante no puede
superar `capacidad_maxima / superficie` de la infraestructura (mismo cálculo
que INC-M02-38-G25 ya usa para eventos de crecimiento, pero evaluado aquí
ANTES de aplicar el cambio, porque este es el flujo que realmente incrementa
`cantidad_actual`).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_ingreso_use_case import (
    RegistrarEventoIngresoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    EventoActivo,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_ingreso_dto import RegistrarEventoIngresoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, ValidationError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo
        self.actualizado: Optional[ActivoBiologico] = None

    def obtener_por_id(self, _id: int):
        return self.activo

    def actualizar_detalle_poblacional(self, activo: ActivoBiologico) -> ActivoBiologico:
        self.actualizado = activo
        return activo


class EventoRepoFake:
    def __init__(self, *, falla: bool = False) -> None:
        self.guardado: Optional[EventoActivo] = None
        self.falla = falla

    def obtener_ultima_fecha(self, _id: int):
        return None

    def guardar(self, evento: EventoActivo) -> EventoActivo:
        if self.falla:
            raise RuntimeError('fallo simulado al guardar el evento')
        self.guardado = evento
        return evento


class InfraPortFake:
    def __init__(
        self,
        superficie: Optional[Decimal] = None,
        capacidad_maxima: Optional[int] = None,
    ) -> None:
        self.superficie = superficie
        self.capacidad_maxima = capacidad_maxima

    def obtener_activa(self, _id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        if self.superficie is None and self.capacidad_maxima is None:
            return InfraestructuraConsulta(
                id_infraestructura=1, nombre='Corral-01', tipo='Corral', es_activo=True,
            )
        return InfraestructuraConsulta(
            id_infraestructura=1, nombre='Corral-01', tipo='Corral', es_activo=True,
            superficie=self.superficie, capacidad_maxima=self.capacidad_maxima,
        )


def _activo_lote(id_estado: int = EstadoActivo.ACTIVO, cantidad_actual: int = 5, peso_promedio=None) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='POBLACIONAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=cantidad_actual,
            cantidad_actual=cantidad_actual,
            peso_promedio=peso_promedio,
        ),
    )


def _activo_individual() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=EstadoActivo.ACTIVO,
        id_usuario=1,
        id_activo_biologico=10,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _dto(cantidad_ingresada=3, fecha_ingreso=None) -> RegistrarEventoIngresoDTO:
    return RegistrarEventoIngresoDTO(
        tipo_ingreso='compra',
        fecha_ingreso=fecha_ingreso or date.today(),
        cantidad_ingresada=cantidad_ingresada,
        motivo_ingreso='reposición de lote',
    )


def _uc(db, activo, evento_repo, infra) -> RegistrarEventoIngresoUseCase:
    return RegistrarEventoIngresoUseCase(
        db=db, activo_repo=ActivoRepoFake(activo), evento_repo=evento_repo, infra_port=infra,
    )


def test_ingreso_incrementa_cantidad_actual() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5)
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo, evento_repo, InfraPortFake())

    resultado = uc.execute(10, _dto(cantidad_ingresada=3), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 8
    assert resultado.ingreso.cantidad_ingresada == 3
    assert resultado.ingreso.tipo == 'compra'
    assert db.commits == 1


def test_ingreso_recalcula_biomasa_si_hay_peso_promedio() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5, peso_promedio=Decimal('2.0'))
    uc = _uc(db, activo, EventoRepoFake(), InfraPortFake())

    uc.execute(10, _dto(cantidad_ingresada=5), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 10
    assert activo.detalle_poblacional.biomasa_total == Decimal('20.0')


def test_ingreso_recalcula_densidad_cuando_hay_superficie() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'))
    uc = _uc(db, activo, EventoRepoFake(), infra)

    uc.execute(10, _dto(cantidad_ingresada=5), _usuario())

    assert activo.detalle_poblacional.densidad == Decimal('1')  # 10 individuos / 10 m²


def test_ingreso_sobre_individual_lanza_tipo_invalido() -> None:
    db = DbFake()
    uc = _uc(db, _activo_individual(), EventoRepoFake(), InfraPortFake())

    with pytest.raises(ValidationError) as exc:
        uc.execute(10, _dto(), _usuario())

    assert exc.value.code == 'TIPO_INVALIDO'


@pytest.mark.parametrize('id_estado', [EstadoActivo.CERRADO, EstadoActivo.BAJA, EstadoActivo.INACTIVO])
def test_ingreso_bloqueado_en_estados_que_no_permiten_eventos(id_estado) -> None:
    db = DbFake()
    uc = _uc(db, _activo_lote(id_estado=id_estado), EventoRepoFake(), InfraPortFake())

    with pytest.raises(ConflictError) as exc:
        uc.execute(10, _dto(), _usuario())

    assert exc.value.code == 'ESTADO_NO_PERMITE_EVENTOS'


def test_ingreso_fecha_futura_lanza_validation_error() -> None:
    db = DbFake()
    uc = _uc(db, _activo_lote(), EventoRepoFake(), InfraPortFake())

    with pytest.raises(ValidationError) as exc:
        uc.execute(10, _dto(fecha_ingreso=date.today() + timedelta(days=1)), _usuario())

    assert exc.value.code == 'FECHA_INGRESO_FUTURA'


def test_ingreso_densidad_resultante_supera_maximo_lanza_409() -> None:
    db = DbFake()
    # capacidad_maxima=10 individuos, superficie=10 m² -> densidad_maxima=1 ind/m².
    # 5 actuales + 6 nuevos = 11 -> densidad 1.1, supera el máximo.
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), capacidad_maxima=10)
    uc = _uc(db, activo, EventoRepoFake(), infra)

    with pytest.raises(ConflictError) as exc:
        uc.execute(10, _dto(cantidad_ingresada=6), _usuario())

    assert exc.value.code == 'DENSIDAD_MAXIMA_SUPERADA'
    assert activo.detalle_poblacional.cantidad_actual == 5  # sin mutar
    assert db.commits == 0


def test_ingreso_densidad_resultante_exactamente_en_el_maximo_se_acepta() -> None:
    db = DbFake()
    # 5 actuales + 5 nuevos = 10 -> densidad exactamente 1.0 == máximo, borde aceptado.
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), capacidad_maxima=10)
    uc = _uc(db, activo, EventoRepoFake(), infra)

    resultado = uc.execute(10, _dto(cantidad_ingresada=5), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 10
    assert resultado is not None


def test_ingreso_sin_capacidad_maxima_configurada_no_bloquea() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), capacidad_maxima=None)
    uc = _uc(db, activo, EventoRepoFake(), infra)

    uc.execute(10, _dto(cantidad_ingresada=1000), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 1005


def test_fallo_al_guardar_evento_revierte_la_transaccion() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5)
    uc = _uc(db, activo, EventoRepoFake(falla=True), InfraPortFake())

    with pytest.raises(RuntimeError, match='fallo simulado'):
        uc.execute(10, _dto(), _usuario())

    assert db.commits == 0
    assert db.rollbacks == 1

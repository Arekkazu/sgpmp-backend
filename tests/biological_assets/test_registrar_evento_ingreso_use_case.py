# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-23 RF-33/34/36/48: capacidad efectiva del área (RFC-012) |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima, ingreso de
individuos"): no existía ningún mecanismo de alta de individuos a un lote --
solo el flujo de BAJA. `RegistrarEventoIngresoUseCase` es la contraparte,
mismo patrón estructural que `RegistrarEventoBajaUseCase` (RF-45), con una
validación adicional que RF-45 no necesita: la carga resultante del área no puede
superar su capacidad efectiva (RFC-012, DEV-23: Σ individuos del área + ingresados ≤
floor(MIN densidad × superficie)), evaluada ANTES de aplicar el cambio, porque este es
el flujo que realmente incrementa `cantidad_actual`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import pytest

import src.shared.fechas as fechas

from src.biological_assets.application.use_cases.gestion.registrar_evento_ingreso_use_case import (
    RegistrarEventoIngresoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    EventoActivo,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.configuration.domain.services.capacidad_area import EspecieDelArea
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_ingreso_dto import RegistrarEventoIngresoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError


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
    """Área con la especie del lote asociada (RFC-012, DEV-23). ``ocupacion`` es la carga
    actual del área (por defecto, solo el lote de 5)."""

    def __init__(
        self,
        superficie: Optional[Decimal] = Decimal('100'),
        densidad: Optional[Decimal] = Decimal('10'),
        ocupacion: int = 5,
    ) -> None:
        self.superficie = superficie
        self.densidad = densidad
        self.ocupacion = ocupacion

    def obtener_activa(self, _id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        return InfraestructuraConsulta(
            id_infraestructura=1, nombre='Corral-01', tipo='Corral', es_activo=True,
            superficie=self.superficie, especies=[EspecieDelArea(1, 'Tilapia', 'PECES', self.densidad)],
        )

    def calcular_ocupacion(self, _id_infraestructura: int) -> int:
        return self.ocupacion

    def bloquear_capacidad(self, _id_infraestructura: int) -> None:
        pass


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


@pytest.fixture
def noche_en_colombia(monkeypatch, en_colombia) -> None:
    # 2026-10-11 22:25 en Colombia == 2026-10-12 03:25 UTC
    monkeypatch.setattr(
        fechas, '_ahora', lambda: datetime(2026, 10, 12, 3, 25, tzinfo=timezone.utc).astimezone(en_colombia),
    )


@pytest.mark.usefixtures('noche_en_colombia')
def test_ingreso_fecha_de_manana_en_colombia_es_futura_aunque_en_utc_ya_sea_hoy() -> None:
    uc = _uc(DbFake(), _activo_lote(), EventoRepoFake(), InfraPortFake())

    with pytest.raises(ValidationError) as exc:
        uc.execute(10, _dto(fecha_ingreso=date(2026, 10, 12)), _usuario())
    assert exc.value.code == 'FECHA_INGRESO_FUTURA'

    uc.execute(10, _dto(fecha_ingreso=date(2026, 10, 11)), _usuario())


@pytest.mark.usefixtures('noche_en_colombia')
def test_ingreso_del_dia_de_creacion_no_queda_antes_de_la_creacion() -> None:
    # trg_fn_evento_fecha_coherente exige fecha >= fecha_creacion: medianoche
    # UTC del 11 caería antes de un lote creado el 11 a las 20:00 (Colombia).
    creacion = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
    activo = _activo_lote()
    activo.fecha_creacion = creacion
    repo = EventoRepoFake()
    uc = _uc(DbFake(), activo, repo, InfraPortFake())

    uc.execute(10, _dto(fecha_ingreso=date(2026, 10, 11)), _usuario())

    assert repo.guardado.fecha == creacion


def test_ingreso_que_supera_la_capacidad_efectiva_es_422_sin_incrementar() -> None:
    db = DbFake()
    # DEV-23: capacidad = floor(1 ind/m² × 10 m²) = 10. 5 en el área + 6 = 11 → 422 (antes 409).
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), densidad=Decimal('1'))
    uc = _uc(db, activo, EventoRepoFake(), infra)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto(cantidad_ingresada=6), _usuario())

    assert exc.value.status_code == 422
    assert exc.value.code == 'CAPACIDAD_EXCEDIDA'
    assert exc.value.field == 'cantidad_ingresada'
    assert activo.detalle_poblacional.cantidad_actual == 5  # sin mutar
    assert db.commits == 0


def test_ingreso_exactamente_en_la_capacidad_se_acepta() -> None:
    db = DbFake()
    # 5 actuales + 5 nuevos = 10 == capacidad: el límite cabe.
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), densidad=Decimal('1'))
    uc = _uc(db, activo, EventoRepoFake(), infra)

    resultado = uc.execute(10, _dto(cantidad_ingresada=5), _usuario())

    assert activo.detalle_poblacional.cantidad_actual == 10
    assert resultado is not None


def test_ingreso_cuenta_a_todo_el_area_y_no_solo_al_lote() -> None:
    # DEV-23: el área aloja el lote (5) y otros 3 individuos; capacidad 10. +3 → 11 → 422,
    # aunque el lote solo (5 + 3 = 8) cabría. Antes se miraba solo el lote.
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), densidad=Decimal('1'), ocupacion=8)

    with pytest.raises(BusinessRuleError) as exc:
        _uc(DbFake(), activo, EventoRepoFake(), infra).execute(10, _dto(cantidad_ingresada=3), _usuario())

    assert exc.value.code == 'CAPACIDAD_EXCEDIDA'


def test_ingreso_con_especie_sin_densidad_es_422() -> None:
    # DEV-23 (H-12.4): antes, sin capacidad configurada no se validaba nada.
    activo = _activo_lote(cantidad_actual=5)
    infra = InfraPortFake(superficie=Decimal('10'), densidad=None)

    with pytest.raises(BusinessRuleError) as exc:
        _uc(DbFake(), activo, EventoRepoFake(), infra).execute(10, _dto(cantidad_ingresada=1000), _usuario())

    assert exc.value.code == 'ESPECIE_SIN_DENSIDAD'
    assert activo.detalle_poblacional.cantidad_actual == 5


def test_fallo_al_guardar_evento_revierte_la_transaccion() -> None:
    db = DbFake()
    activo = _activo_lote(cantidad_actual=5)
    uc = _uc(db, activo, EventoRepoFake(falla=True), InfraPortFake())

    with pytest.raises(RuntimeError, match='fallo simulado'):
        uc.execute(10, _dto(), _usuario())

    assert db.commits == 0
    assert db.rollbacks == 1

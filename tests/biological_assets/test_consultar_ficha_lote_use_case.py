"""RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima, ingreso de
individuos"): no existía un endpoint/caso de uso propio de "gestión de lote"
con la ficha operativa completa (cantidad_actual + peso_promedio +
biomasa_total + densidad + estado + historial en una sola vista) -- distinto
de la ficha integral genérica de RF-47 (sin densidad ni densidad_maxima).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_ficha_lote_use_case import (
    ConsultarFichaLoteUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    PaginaHistorial,
    RegistroHistorial,
)
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsulta
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


class DbFake:
    def commit(self) -> None:
        pass


class ActivoRepoFake:
    def __init__(self, activo: Optional[ActivoBiologico]) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


class InfraPortFake:
    def __init__(self, superficie=None, capacidad_maxima=None, nombre='Corral-01') -> None:
        self.superficie = superficie
        self.capacidad_maxima = capacidad_maxima
        self.nombre = nombre

    def obtener_activa(self, _id: int) -> InfraestructuraConsulta:
        return InfraestructuraConsulta(
            id_infraestructura=1, nombre=self.nombre, tipo='Corral', es_activo=True,
            superficie=self.superficie, capacidad_maxima=self.capacidad_maxima,
        )


class EspeciePortFake:
    def __init__(self, nombre: Optional[str] = 'Bovino') -> None:
        self.nombre = nombre

    def obtener_activa(self, _id: int):
        if self.nombre is None:
            return None
        return EspecieConsulta(id_especie=1, nombre=self.nombre, es_activo=True)


class TransferenciaRepoFake:
    def __init__(self, registros: Optional[list[RegistroHistorial]] = None) -> None:
        self.registros = registros or []
        self.ultima_llamada: Optional[dict] = None

    def consultar_historial(self, **kwargs) -> PaginaHistorial:
        self.ultima_llamada = kwargs
        return PaginaHistorial(
            registros=self.registros,
            total_registros=len(self.registros),
            pagina_actual=1,
            total_paginas=1,
            registros_por_pagina=kwargs.get('page_size', 10),
        )


def _activo_lote(
    id_estado: int = EstadoActivo.ACTIVO,
    cantidad_inicial: int = 10,
    cantidad_actual: int = 8,
) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='POBLACIONAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
        identificador='LOTE-01',
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
        nombre_estado='ACTIVO',
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=cantidad_inicial,
            cantidad_actual=cantidad_actual,
            peso_promedio_inicial=Decimal('1.0'),
            peso_promedio=Decimal('1.5'),
            biomasa_total=Decimal('12.0'),
            densidad=Decimal('0.8'),
        ),
    )


def _activo_individual() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1, tipo='INDIVIDUAL', origen_financiero='compra',
        id_infraestructura=1, id_estado=EstadoActivo.ACTIVO, id_usuario=1,
        id_activo_biologico=10,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _uc(activo, infra=None, especie=None, transferencia=None) -> ConsultarFichaLoteUseCase:
    return ConsultarFichaLoteUseCase(
        db=DbFake(),
        activo_repo=ActivoRepoFake(activo),
        infra_port=infra or InfraPortFake(),
        especie_port=especie or EspeciePortFake(),
        transferencia_repo=transferencia or TransferenciaRepoFake(),
    )


def test_ficha_lote_expone_metricas_completas() -> None:
    activo = _activo_lote()
    uc = _uc(activo)

    ficha = uc.execute(10, _usuario())

    assert ficha.id_activo_biologico == 10
    assert ficha.identificador == 'LOTE-01'
    assert ficha.cantidad_inicial == 10
    assert ficha.cantidad_actual == 8
    assert ficha.peso_promedio == Decimal('1.5')
    assert ficha.biomasa_total == Decimal('12.0')
    assert ficha.densidad == Decimal('0.8')
    assert ficha.estado_actual == 'ACTIVO'
    assert ficha.especie == 'Bovino'
    assert ficha.infraestructura_asociada == 'Corral-01'


def test_ficha_lote_incluye_densidad_maxima_cuando_hay_capacidad_configurada() -> None:
    activo = _activo_lote()
    infra = InfraPortFake(superficie=Decimal('10'), capacidad_maxima=15)
    uc = _uc(activo, infra=infra)

    ficha = uc.execute(10, _usuario())

    assert ficha.densidad_maxima == Decimal('1.5')  # 15 / 10


def test_ficha_lote_sin_capacidad_maxima_configurada_deja_densidad_maxima_en_none() -> None:
    activo = _activo_lote()
    uc = _uc(activo, infra=InfraPortFake(superficie=Decimal('10'), capacidad_maxima=None))

    ficha = uc.execute(10, _usuario())

    assert ficha.densidad_maxima is None


def test_ficha_lote_incluye_historial() -> None:
    activo = _activo_lote()
    registros = [
        RegistroHistorial(
            categoria='INGRESO', fecha_evento=datetime.now(timezone.utc),
            descripcion='Ingreso de 3 individuos', detalle_especifico={},
            usuario_responsable='Juan Pérez', modulo_origen='modulo2',
        ),
    ]
    transferencia = TransferenciaRepoFake(registros)
    uc = _uc(activo, transferencia=transferencia)

    ficha = uc.execute(10, _usuario())

    assert ficha.total_registros_historial == 1
    assert ficha.historial[0].categoria == 'INGRESO'
    assert transferencia.ultima_llamada['id_activo'] == 10


def test_ficha_lote_sobre_activo_inexistente_lanza_not_found() -> None:
    uc = _uc(None)

    with pytest.raises(NotFoundError):
        uc.execute(999, _usuario())


def test_ficha_lote_sobre_individual_lanza_tipo_invalido() -> None:
    uc = _uc(_activo_individual())

    with pytest.raises(ValidationError) as exc:
        uc.execute(10, _usuario())

    assert exc.value.code == 'TIPO_INVALIDO'


def test_ficha_lote_sin_especie_configurada_no_falla() -> None:
    activo = _activo_lote()
    uc = _uc(activo, especie=EspeciePortFake(nombre=None))

    ficha = uc.execute(10, _usuario())

    assert ficha.especie is None

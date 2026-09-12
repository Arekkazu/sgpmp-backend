"""RF-50 (INC-M02-97-G95): no se deben exponer datos consolidados cuando el
activo mantiene una asociación vigente hacia una infraestructura inactiva
(inconsistencia jerárquica) — debe rechazarse con 409 antes de consultar.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_datos_consolidados_use_case import (
    ConsultarDatosConsolidadosUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DatosConsolidados,
    HistorialInfraestructura,
)
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico | None, asociacion: HistorialInfraestructura | None) -> None:
        self.activo = activo
        self.asociacion = asociacion

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return self.asociacion


class IndicadoresRepoFake:
    def __init__(self) -> None:
        self.llamado = False

    def obtener_datos_consolidados(self, **kwargs) -> DatosConsolidados:
        self.llamado = True
        return DatosConsolidados(
            id_activo_biologico=kwargs['id_activo'],
            identificador='ID-1',
            tipo_activo='INDIVIDUAL',
            especie='bovino',
            estado_actual='ACTIVO',
            infraestructura_asociada='Corral 1',
            fase_productiva_activa=None,
            fecha_generacion=datetime.now(timezone.utc),
        )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _activo(id_activo=289) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=49,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=id_activo,
    )


def _uc(activo, asociacion, indicadores_repo=None):
    return ConsultarDatosConsolidadosUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo, asociacion),
        indicadores_repo=indicadores_repo or IndicadoresRepoFake(),
        bitacora_repo=None,
    )


def test_rechaza_cuando_infraestructura_asociada_esta_inactiva():
    asociacion = HistorialInfraestructura(
        id_historial=236,
        id_activo_biologico=289,
        id_infraestructura=49,
        nombre_infraestructura='Corral 49',
        tipo_infraestructura='CORRAL',
        fecha_inicio=datetime(2026, 6, 1, tzinfo=timezone.utc),
        fecha_fin=None,
        es_activo_infraestructura=False,
    )
    indicadores_repo = IndicadoresRepoFake()
    uc = _uc(_activo(), asociacion, indicadores_repo)

    with pytest.raises(ConflictError) as exc:
        uc.execute(289, DatosConsolidadosDTO(), _usuario())

    assert exc.value.code == 'INCONSISTENCIA_JERARQUICA'
    assert indicadores_repo.llamado is False


def test_permite_cuando_infraestructura_asociada_esta_activa():
    asociacion = HistorialInfraestructura(
        id_historial=1,
        id_activo_biologico=279,
        id_infraestructura=1,
        nombre_infraestructura='Corral 1',
        tipo_infraestructura='CORRAL',
        fecha_inicio=datetime(2026, 6, 1, tzinfo=timezone.utc),
        fecha_fin=None,
        es_activo_infraestructura=True,
    )
    indicadores_repo = IndicadoresRepoFake()
    uc = _uc(_activo(279), asociacion, indicadores_repo)

    resultado = uc.execute(279, DatosConsolidadosDTO(), _usuario())

    assert resultado.id_activo_biologico == 279
    assert indicadores_repo.llamado is True


def test_permite_cuando_no_hay_asociacion_vigente():
    uc = _uc(_activo(279), None)

    resultado = uc.execute(279, DatosConsolidadosDTO(), _usuario())

    assert resultado.id_activo_biologico == 279


def test_activo_inexistente_lanza_not_found():
    uc = _uc(None, None)

    with pytest.raises(NotFoundError):
        uc.execute(99999, DatosConsolidadosDTO(), _usuario())

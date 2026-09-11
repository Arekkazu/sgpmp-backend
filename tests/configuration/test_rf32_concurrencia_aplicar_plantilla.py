"""Regresión RF-32: la concurrencia optimista debe comparar fecha_actualizacion,
no fecha_creacion (que es inmutable y nunca detectaría una edición real)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import (
    AplicarPlantillaUseCase,
)
from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import PreconditionFailedError

FECHA_ACTUALIZACION_DB = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RepoVacioFake:
    """Cubre ciclo/metrica/umbral/patologia: sin datos previos, sin categorías en el snapshot."""

    def desactivar_todos_por_especie(self, _id_especie):
        pass

    desactivar_todas_por_especie = desactivar_todos_por_especie

    def eliminar_todas_de_especie(self, _id_especie):
        pass

    def listar_por_especie(self, _id_especie, solo_activas: bool = True):
        return []


class AplicacionRepoFake:
    def __init__(self) -> None:
        self.guardada = None

    def guardar(self, aplicacion: AplicacionPlantilla) -> AplicacionPlantilla:
        self.guardada = aplicacion
        aplicacion.id_aplicacion_plantilla = 1
        return aplicacion


def _plantilla() -> Plantilla:
    return Plantilla.crear(
        id_especie=1,
        id_usuario=1,
        template_name="plantilla-test",
        params_snapshot={"schema_version": 1},
        version=1,
        fecha_creacion=datetime.now(timezone.utc),
    )


def _especie_destino() -> Especie:
    especie = Especie.crear(
        nombre=NombreEspecie("Tilapia"),
        descripcion=None,
        fecha_creacion=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    especie.id_especie = 5
    especie.fecha_actualizacion = FECHA_ACTUALIZACION_DB
    return especie


def _use_case(plantilla_repo, especie_repo) -> AplicarPlantillaUseCase:
    repo_vacio = RepoVacioFake()
    return AplicarPlantillaUseCase(
        db=DbFake(),
        plantilla_repo=plantilla_repo,
        especie_repo=especie_repo,
        ciclo_repo=repo_vacio,
        metrica_repo=repo_vacio,
        umbral_repo=repo_vacio,
        patologia_repo=repo_vacio,
        aplicacion_repo=AplicacionRepoFake(),
    )


class PlantillaRepoFake:
    def obtener_por_id(self, _id_plantilla):
        return _plantilla()


class EspecieRepoFake:
    def obtener_por_id(self, _id_especie):
        return _especie_destino()


def test_fecha_actualizacion_coincidente_permite_aplicar():
    use_case = _use_case(PlantillaRepoFake(), EspecieRepoFake())
    dto = AplicarPlantillaDTO(
        id_especie_destino=5,
        fecha_actualizacion_especie_destino=FECHA_ACTUALIZACION_DB,
    )
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    resultado = use_case.execute(1, dto, usuario)

    assert resultado.id_aplicacion_plantilla == 1
    assert use_case.db.commits == 1


def test_fecha_actualizacion_distinta_lanza_412():
    use_case = _use_case(PlantillaRepoFake(), EspecieRepoFake())
    dto = AplicarPlantillaDTO(
        id_especie_destino=5,
        fecha_actualizacion_especie_destino=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    with pytest.raises(PreconditionFailedError) as exc_info:
        use_case.execute(1, dto, usuario)

    assert exc_info.value.code == "CONFLICTO_CONCURRENCIA"
    assert use_case.db.commits == 0


def test_fecha_creacion_desincronizada_ya_no_bloquea():
    """Antes del fix, un fecha_creacion distinta (irrelevante) rechazaba la operación.
    Ahora solo importa fecha_actualizacion: la aplicación debe completarse."""
    especie_repo = EspecieRepoFake()

    class EspecieRepoConCreacionDistinta(EspecieRepoFake):
        def obtener_por_id(self, id_especie):
            especie = super().obtener_por_id(id_especie)
            especie.fecha_creacion = datetime(1999, 1, 1, tzinfo=timezone.utc)
            return especie

    use_case = _use_case(PlantillaRepoFake(), EspecieRepoConCreacionDistinta())
    dto = AplicarPlantillaDTO(
        id_especie_destino=5,
        fecha_actualizacion_especie_destino=FECHA_ACTUALIZACION_DB,
    )
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    resultado = use_case.execute(1, dto, usuario)

    assert use_case.db.commits == 1
    assert resultado.id_aplicacion_plantilla == 1

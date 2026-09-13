"""TC-M09-G123 (TC-M09-237/238/239): transiciones de estado de la plantilla durante
'aplicar' (PUBLICADA -> EN APLICACIÓN -> PUBLICADA con contador incrementado, o
PUBLICADA sin cambios tras un rollback).

La ficha pide, para cada sub-caso, verificar un ciclo de vida de estados
(EST-07) y un contador de usos sobre la plantilla. Este archivo deja evidencia,
a dos niveles, de que ese ciclo de vida no existe en el sistema:

1. Estructural: ni la entidad de dominio `Plantilla`, ni el modelo ORM
   `PlantillaModel` (tabla `modulo9.plantillas`), ni el contrato
   `PlantillaRepository` tienen ningún campo, columna o método relacionado con
   un estado o un contador de usos. `PlantillaRepository` solo expone
   `obtener_por_id`, `existe_nombre`, `listar_todas` y `guardar` (inserción);
   no existe ningún método de actualización.
2. De comportamiento: `AplicarPlantillaUseCase.execute()` nunca vuelve a
   escribir la plantilla de origen, ni cuando la aplicación es exitosa ni
   cuando falla y hace rollback. Solo la lee una vez al principio
   (`obtener_por_id`) para tomar su `params_snapshot`.

Como la plantilla nunca es objeto de una segunda escritura, no hay ningún
punto del código donde pudiera aparecer un estado transitorio 'EN APLICACIÓN',
ni un incremento de contador tras el éxito, ni una reversión tras el fallo:
simplemente no hay nada que transicionar.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import (
    AplicarPlantillaUseCase,
)
from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.configuration.infrastructure.models.plantilla_model import PlantillaModel
from src.identity_access.infrastructure.dependencies import UsuarioActual

FECHA_ACTUALIZACION_DB = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)

PALABRAS_DE_ESTADO_O_CONTADOR = ("estado", "status", "contador", "usos", "uso")


# ---------------------------------------------------------------------------
# TC-M09-237 — no existe ningún campo/columna/método de estado o contador
# ---------------------------------------------------------------------------

def test_tc_m09_237_la_entidad_plantilla_no_tiene_campo_de_estado_ni_contador():
    campos = [f.name for f in dataclasses.fields(Plantilla)]
    assert campos == [
        "id_especie",
        "id_usuario",
        "template_name",
        "params_snapshot",
        "version",
        "fecha_creacion",
        "id_plantilla",
    ], "la lista de campos de Plantilla cambio -- revisar si se agrego un estado o contador"
    for campo in campos:
        for palabra in PALABRAS_DE_ESTADO_O_CONTADOR:
            assert palabra not in campo.lower(), (
                f"el campo '{campo}' de la entidad Plantilla sugiere un estado o "
                f"contador de usos, pero la ficha requiere confirmar que no existe ninguno"
            )


def test_tc_m09_237_la_tabla_plantillas_no_tiene_columna_de_estado_ni_contador():
    columnas = list(PlantillaModel.__table__.columns.keys())
    assert columnas == [
        "id_plantilla",
        "id_especie",
        "id_usuario",
        "template_name",
        "params_snapshot",
        "version",
        "fecha_creacion",
    ], "las columnas de modulo9.plantillas cambiaron -- revisar si se agrego un estado o contador"
    for columna in columnas:
        for palabra in PALABRAS_DE_ESTADO_O_CONTADOR:
            assert palabra not in columna.lower(), (
                f"la columna '{columna}' de modulo9.plantillas sugiere un estado o "
                f"contador de usos, pero la ficha requiere confirmar que no existe ninguno"
            )


def test_tc_m09_237_el_repositorio_de_plantillas_no_expone_ningun_metodo_de_actualizacion():
    metodos_publicos = {nombre for nombre in dir(PlantillaRepository) if not nombre.startswith("_")}
    assert metodos_publicos == {"obtener_por_id", "existe_nombre", "listar_todas", "guardar"}, (
        "PlantillaRepository expone un metodo nuevo -- revisar si permite actualizar "
        "el estado o el contador de usos de una plantilla existente"
    )
    # 'guardar' es exclusivamente de insercion (ver su propio docstring: "Inserta una
    # plantilla nueva"). No existe 'actualizar', 'cambiar_estado' ni 'incrementar_uso'.


# ---------------------------------------------------------------------------
# Infraestructura de prueba compartida por TC-M09-238 y TC-M09-239
# (mismo patron de fakes que tests/configuration/test_rf32_concurrencia_aplicar_plantilla.py)
# ---------------------------------------------------------------------------

class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RepoVacioFake:
    """Cubre ciclo/metrica/umbral/patologia cuando el snapshot no trae esa categoria."""

    def desactivar_todos_por_especie(self, _id_especie):
        pass

    desactivar_todas_por_especie = desactivar_todos_por_especie

    def eliminar_todas_de_especie(self, _id_especie):
        pass

    def listar_por_especie(self, _id_especie, solo_activas: bool = True):
        return []


class CicloRepoQueFalla(RepoVacioFake):
    """Simula un error de persistencia (p. ej. de base de datos) al escribir el ciclo."""

    def guardar_desde_snapshot(self, _datos, _id_especie):
        raise RuntimeError("fallo simulado de persistencia en base de datos")


class AplicacionRepoFake:
    def guardar(self, aplicacion: AplicacionPlantilla) -> AplicacionPlantilla:
        aplicacion.id_aplicacion_plantilla = 1
        return aplicacion


class PlantillaRepoRastreada:
    """Registra cuantas veces se le pide escribir (guardar) la plantilla de origen."""

    def __init__(self, plantilla: Plantilla) -> None:
        self._plantilla = plantilla
        self.veces_que_se_llamo_guardar = 0

    def obtener_por_id(self, _id_plantilla):
        return self._plantilla

    def guardar(self, plantilla: Plantilla) -> Plantilla:
        self.veces_que_se_llamo_guardar += 1
        return plantilla


class EspecieRepoFake:
    def obtener_por_id(self, _id_especie):
        especie = Especie.crear(
            nombre=NombreEspecie("Tilapia"),
            descripcion=None,
            fecha_creacion=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        especie.id_especie = 5
        especie.fecha_actualizacion = FECHA_ACTUALIZACION_DB
        return especie


def _plantilla(params_snapshot: dict) -> Plantilla:
    plantilla = Plantilla.crear(
        id_especie=1,
        id_usuario=1,
        template_name="plantilla-tc-m09-123",
        params_snapshot=params_snapshot,
        version=1,
        fecha_creacion=datetime.now(timezone.utc),
    )
    plantilla.id_plantilla = 1
    return plantilla


def _dto() -> AplicarPlantillaDTO:
    return AplicarPlantillaDTO(
        id_especie_destino=5,
        fecha_actualizacion_especie_destino=FECHA_ACTUALIZACION_DB,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


# ---------------------------------------------------------------------------
# TC-M09-238 — aplicación exitosa: la plantilla de origen no se vuelve a escribir
# ---------------------------------------------------------------------------

def test_tc_m09_238_una_aplicacion_exitosa_no_reescribe_ni_versiona_la_plantilla_origen():
    plantilla = _plantilla({"schema_version": 1})
    version_antes = plantilla.version
    template_name_antes = plantilla.template_name
    plantilla_repo = PlantillaRepoRastreada(plantilla)

    use_case = AplicarPlantillaUseCase(
        db=DbFake(),
        plantilla_repo=plantilla_repo,
        especie_repo=EspecieRepoFake(),
        ciclo_repo=RepoVacioFake(),
        metrica_repo=RepoVacioFake(),
        umbral_repo=RepoVacioFake(),
        patologia_repo=RepoVacioFake(),
        aplicacion_repo=AplicacionRepoFake(),
    )

    resultado = use_case.execute(1, _dto(), _usuario())

    assert use_case.db.commits == 1
    assert resultado.id_aplicacion_plantilla == 1
    assert plantilla_repo.veces_que_se_llamo_guardar == 0, (
        "la ficha esperaba que, tras una aplicacion exitosa, la plantilla volviera a "
        "PUBLICADA con su contador de usos incrementado en base de datos; pero el "
        "caso de uso nunca vuelve a escribir la plantilla de origen -- no hay ningun "
        "campo de estado ni de contador que se pueda incrementar"
    )
    assert plantilla.version == version_antes
    assert plantilla.template_name == template_name_antes


# ---------------------------------------------------------------------------
# TC-M09-239 — aplicación fallida con rollback: la plantilla de origen tampoco se toca
# ---------------------------------------------------------------------------

def test_tc_m09_239_un_fallo_con_rollback_no_reescribe_ni_consume_la_plantilla_origen():
    plantilla = _plantilla({"schema_version": 1, "ciclos_biologicos": [{"nombre": "x", "duracion_dias": 10}]})
    version_antes = plantilla.version
    plantilla_repo = PlantillaRepoRastreada(plantilla)

    use_case = AplicarPlantillaUseCase(
        db=DbFake(),
        plantilla_repo=plantilla_repo,
        especie_repo=EspecieRepoFake(),
        ciclo_repo=CicloRepoQueFalla(),
        metrica_repo=RepoVacioFake(),
        umbral_repo=RepoVacioFake(),
        patologia_repo=RepoVacioFake(),
        aplicacion_repo=AplicacionRepoFake(),
    )

    with pytest.raises(RuntimeError):
        use_case.execute(1, _dto(), _usuario())

    assert use_case.db.commits == 0
    assert use_case.db.rollbacks == 1
    assert plantilla_repo.veces_que_se_llamo_guardar == 0, (
        "la ficha esperaba que, tras un fallo con rollback, la plantilla volviera a "
        "PUBLICADA sin cambios; en la practica nunca llega a cambiar porque el caso de "
        "uso jamas vuelve a escribirla, ni siquiera para 'devolverla' a un estado anterior"
    )
    assert plantilla.version == version_antes
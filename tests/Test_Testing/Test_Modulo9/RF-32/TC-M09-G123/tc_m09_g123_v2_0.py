"""TC-M09-G123 v2.0 - Transiciones del ciclo de vida de la plantilla durante la aplicacion.

Reformulacion de TC-M09-237/238/239 acordada con QA: la ficha original asumia un
ciclo de vida PUBLICADA -> EN APLICACION -> PUBLICADA con un contador de usos que
el sistema real nunca implemento (confirmado por revision de codigo: la entidad
Plantilla, el modelo ORM y PlantillaRepository no tienen ningun campo de estado ni
contador, y estan documentados como "inmutables por diseno: la version es la
identidad"). En vez de forzar una prueba sobre un mecanismo que no existe, estas
3 pruebas verifican la garantia real y equivalente que SI ofrece el diseno actual:

  TC-M09-237 v2.0: la plantilla origen permanece de solo lectura durante TODO el
    proceso de aplicacion (no hay ningun estado transitorio que verificar porque
    la plantilla nunca se reescribe).
  TC-M09-238 v2.0: una aplicacion EXITOSA registra el uso en un historial
    independiente (aplicaciones_plantillas / AplicacionPlantillaRepository.guardar),
    sin modificar ni versionar la plantilla origen (PlantillaRepository.guardar
    nunca se vuelve a invocar).
  TC-M09-239 v2.0: un fallo con rollback tampoco deja la plantilla origen
    modificada ni consumida -- se comporta igual que el camino de exito en cuanto
    a la inmutabilidad de la plantilla.

Cada asercion expresa el comportamiento REQUERIDO por el diseno vigente: si algun
dia una aplicacion (exitosa o fallida) llegara a reescribir la plantilla origen,
estas pruebas fallarian (rojo), detectando una regresion sobre la inmutabilidad.

Ejecutar con:
    python -m pytest tc_m09_g123_v2_0.py -v --html=resultado-tc-m09-g123-v2_0.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import (
    AplicarPlantillaUseCase,
)
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO


class _EspecieFake:
    """Stand-in minimo para la entidad Especie que el use case consulta."""

    def __init__(self, es_activo: bool = True, fecha_actualizacion=None):
        self.es_activo = es_activo
        self.fecha_actualizacion = fecha_actualizacion


class _UsuarioActualFake:
    def __init__(self, id_usuario: int = 47):
        self.id_usuario = id_usuario


def _plantilla_valida(id_plantilla: int = 92) -> Plantilla:
    return Plantilla(
        id_especie=41,
        id_usuario=47,
        template_name="QA-G123-v2",
        params_snapshot={
            "schema_version": 1,
            "ciclos_biologicos": [{"nombre": "Etapa Test G123", "duracion_dias": 30}],
        },
        version=1,
        fecha_creacion=datetime.now(timezone.utc),
        id_plantilla=id_plantilla,
    )


def _construir_use_case(plantilla: Plantilla, especie_destino: _EspecieFake):
    """Arma un AplicarPlantillaUseCase con todos los repos mockeados (sin BD real)."""
    db = MagicMock()
    plantilla_repo = MagicMock()
    plantilla_repo.obtener_por_id.return_value = plantilla

    especie_repo = MagicMock()
    especie_repo.obtener_por_id.return_value = especie_destino

    ciclo_repo = MagicMock()
    metrica_repo = MagicMock()
    umbral_repo = MagicMock()
    patologia_repo = MagicMock()

    # _capturar_estado() lee estas 4 listas antes y despues de escribir.
    ciclo_repo.listar_por_especie.return_value = []
    metrica_repo.listar_por_especie.return_value = []
    umbral_repo.listar_por_especie.return_value = []
    patologia_repo.listar_por_especie.return_value = []

    aplicacion_repo = MagicMock()
    aplicacion_repo.guardar.side_effect = lambda aplicacion: aplicacion

    use_case = AplicarPlantillaUseCase(
        db=db,
        plantilla_repo=plantilla_repo,
        especie_repo=especie_repo,
        ciclo_repo=ciclo_repo,
        metrica_repo=metrica_repo,
        umbral_repo=umbral_repo,
        patologia_repo=patologia_repo,
        aplicacion_repo=aplicacion_repo,
    )
    return use_case, dict(
        db=db,
        plantilla_repo=plantilla_repo,
        especie_repo=especie_repo,
        ciclo_repo=ciclo_repo,
        metrica_repo=metrica_repo,
        umbral_repo=umbral_repo,
        patologia_repo=patologia_repo,
        aplicacion_repo=aplicacion_repo,
    )


def test_tc_m09_237_v2_la_plantilla_origen_permanece_de_solo_lectura_durante_la_aplicacion():
    """TC-M09-237 v2.0: durante TODO el proceso de aplicacion (exitoso), el unico
    metodo del repositorio de plantillas que se invoca es obtener_por_id (lectura).
    guardar() -- el unico metodo de escritura que expone PlantillaRepository --
    nunca debe llamarse: eso confirmaria que la plantilla origen no se reescribe
    ni transiciona a ningun estado intermedio.
    """
    plantilla = _plantilla_valida()
    especie_destino = _EspecieFake(es_activo=True, fecha_actualizacion=None)
    use_case, repos = _construir_use_case(plantilla, especie_destino)
    dto = AplicarPlantillaDTO(id_especie_destino=39, fecha_actualizacion_especie_destino=None)
    usuario = _UsuarioActualFake()

    use_case.execute(id_plantilla=92, dto=dto, usuario_actual=usuario)

    repos["plantilla_repo"].obtener_por_id.assert_called_once_with(92)
    repos["plantilla_repo"].guardar.assert_not_called()


def test_tc_m09_238_v2_una_aplicacion_exitosa_registra_el_uso_sin_modificar_la_plantilla_origen():
    """TC-M09-238 v2.0: una aplicacion exitosa debe quedar registrada en el
    historial de aplicaciones (AplicacionPlantillaRepository.guardar, exactamente
    una vez, referenciando la plantilla correcta) -- esta es la trazabilidad real
    que reemplaza al 'contador de usos' que la ficha original asumia -- y la
    plantilla origen no debe versionarse ni modificarse en el proceso.
    """
    plantilla = _plantilla_valida(id_plantilla=92)
    especie_destino = _EspecieFake(es_activo=True, fecha_actualizacion=None)
    use_case, repos = _construir_use_case(plantilla, especie_destino)
    dto = AplicarPlantillaDTO(id_especie_destino=39, fecha_actualizacion_especie_destino=None)
    usuario = _UsuarioActualFake()

    resultado = use_case.execute(id_plantilla=92, dto=dto, usuario_actual=usuario)

    repos["aplicacion_repo"].guardar.assert_called_once()
    aplicacion_guardada = repos["aplicacion_repo"].guardar.call_args[0][0]
    assert aplicacion_guardada.id_plantilla == 92
    repos["plantilla_repo"].guardar.assert_not_called()
    repos["db"].commit.assert_called_once()
    assert resultado is not None


def test_tc_m09_239_v2_un_fallo_con_rollback_no_deja_la_plantilla_origen_modificada():
    """TC-M09-239 v2.0: si la aplicacion falla a mitad de las escrituras (rollback
    real), la plantilla origen tampoco debe quedar modificada ni consumida --
    debe comportarse exactamente igual que el camino de exito en cuanto a su
    propia inmutabilidad, sin importar el resultado de la operacion.
    """
    plantilla = _plantilla_valida(id_plantilla=92)
    especie_destino = _EspecieFake(es_activo=True, fecha_actualizacion=None)
    use_case, repos = _construir_use_case(plantilla, especie_destino)
    # Forzamos el fallo en la escritura de ciclos, a mitad del bloque try.
    repos["ciclo_repo"].guardar_desde_snapshot.side_effect = RuntimeError(
        "Error simulado de base de datos"
    )
    dto = AplicarPlantillaDTO(id_especie_destino=39, fecha_actualizacion_especie_destino=None)
    usuario = _UsuarioActualFake()

    with pytest.raises(RuntimeError):
        use_case.execute(id_plantilla=92, dto=dto, usuario_actual=usuario)

    repos["db"].rollback.assert_called_once()
    repos["db"].commit.assert_not_called()
    repos["plantilla_repo"].guardar.assert_not_called()
    repos["aplicacion_repo"].guardar.assert_not_called()
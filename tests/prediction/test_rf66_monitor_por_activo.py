# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
"""Estado sanitario: un animal sin eventos recientes no desaparece por el volumen de las cámaras.

Las consultas se verificaron contra DEV (con por_activo=3 aparecen los 6 activos, también los que
quedaban fuera de las 200 más recientes).
"""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from src.prediction.application.use_cases.monitor.listar_inferencias_use_case import ListarInferenciasUseCase
from src.prediction.application.use_cases.monitor.listar_riesgo_contagio_use_case import (
    ListarRiesgoContagioUseCase,
)
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.shared.errors import ValidationError


def test_por_activo_llega_al_repositorio_y_sin_el_todo_sigue_igual():
    repo = Mock()
    ListarInferenciasUseCase(repo).execute(ids_fincas=[1], por_activo=30)
    assert repo.listar_inferencias.call_args.kwargs["por_activo"] == 30
    ListarRiesgoContagioUseCase(repo).execute(ids_fincas=[1])
    assert repo.listar_riesgo_contagio.call_args.kwargs["por_activo"] is None


@pytest.mark.parametrize("por_activo", [0, 51])
def test_por_activo_fuera_de_rango_es_400(por_activo):
    with pytest.raises(ValidationError) as e:
        ListarInferenciasUseCase(Mock()).execute(ids_fincas=None, por_activo=por_activo)
    assert e.value.code == "POR_ACTIVO_INVALIDO"


def test_repositorio_restringe_a_los_ultimos_de_cada_activo_y_no_corta_por_limite():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.side_effect = [
        [{"id": 11}, {"id": 12}, {"id": 13}],  # los últimos de cada activo
        [],  # la consulta del listado
    ]
    SqlAlchemyMonitorPrediccionRepository(db).listar_riesgo_contagio(
        ids_fincas=None, nivel_riesgo=None, desde=None, hasta=None, limite=1, por_activo=2,
    )
    (_, previos), (_, listado) = (c.args for c in db.execute.call_args_list)
    assert previos["por_activo"] == 2
    assert (listado["ids"], listado["limite"]) == ([11, 12, 13], 3)

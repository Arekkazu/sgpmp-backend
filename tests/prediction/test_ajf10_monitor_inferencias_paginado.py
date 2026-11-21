# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-10 RF-66: monitor paginado, filtro por animal, solo con alerta y sin pruebas |
"""AJF-10: el monitor pedía las últimas 200 y no podía filtrar por animal ni saber cuántas hay."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from src.prediction.application.use_cases.monitor.listar_inferencias_use_case import ListarInferenciasUseCase
from src.prediction.application.use_cases.monitor.paginar_inferencias_use_case import PaginarInferenciasUseCase
from src.prediction.domain.entities.monitor_prediccion import IndicadoresInferencias
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.shared.errors import ValidationError


def test_pagina_calcula_el_desplazamiento_y_pasa_los_mismos_filtros_al_conteo():
    repo = Mock()
    repo.listar_inferencias.return_value = []
    repo.contar_inferencias.return_value = IndicadoresInferencias(total=60, en_riesgo=5, con_alerta=2, animales_distintos=3)
    r = PaginarInferenciasUseCase(repo).execute(
        ids_fincas=[1], pagina=3, por_pagina=25, id_activo_biologico=4, solo_con_alerta=True, incluir_sombra=False,
    )
    lista = repo.listar_inferencias.call_args.kwargs
    assert (lista["limite"], lista["desplazamiento"]) == (25, 50)
    conteo = repo.contar_inferencias.call_args.kwargs
    for k in ("id_activo_biologico", "solo_con_alerta", "incluir_sombra", "ids_fincas"):
        assert conteo[k] == lista[k]
    assert r.indicadores.total == 60 and r.pagina == 3


@pytest.mark.parametrize("pagina, por_pagina, codigo", [(0, 25, "PAGINA_INVALIDA"), (1, 0, "POR_PAGINA_INVALIDO"), (1, 201, "POR_PAGINA_INVALIDO")])
def test_pagina_fuera_de_rango_es_400(pagina, por_pagina, codigo):
    with pytest.raises(ValidationError) as e:
        PaginarInferenciasUseCase(Mock()).execute(ids_fincas=None, pagina=pagina, por_pagina=por_pagina)
    assert e.value.code == codigo


def test_listado_sin_filtros_nuevos_sigue_igual_para_estado_sanitario():
    repo = Mock()
    ListarInferenciasUseCase(repo).execute(ids_fincas=[1], por_activo=30)
    kw = repo.listar_inferencias.call_args.kwargs
    assert (kw["id_activo_biologico"], kw["solo_con_alerta"], kw["incluir_sombra"]) == (None, False, True)


def test_repositorio_manda_los_filtros_como_parametros():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"total": 7, "en_riesgo": 2, "con_alerta": 1, "animales_distintos": 2},
    ]
    ind = SqlAlchemyMonitorPrediccionRepository(db).contar_inferencias(
        ids_fincas=None, tipo_modelo=None, nivel_riesgo=None, desde=None, hasta=None,
        id_activo_biologico=4, incluir_sombra=False,
    )
    sql, params = db.execute.call_args.args
    assert "count(DISTINCT r.id_activo_biologico)" in str(sql)
    assert (params["activo"], params["con_sombra"], params["solo_alerta"]) == (4, False, False)
    assert ind == IndicadoresInferencias(total=7, en_riesgo=2, con_alerta=1, animales_distintos=2)

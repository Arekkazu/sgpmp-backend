"""[RF-43] ``GET /{id_activo}/metricas`` marca solo las métricas que admite la fase activa."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.biological_assets.application.use_cases.gestion.listar_metricas_activo_use_case import (
    ListarMetricasActivoUseCase,
)
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.shared.errors import NotFoundError

_METRICAS = [
    MetricaProductiva(id_metrica_produccion=15, tipo_producto='peso vivo', unidad_medida='kg', aplica_a_tipo_activo='AMBOS'),
    MetricaProductiva(id_metrica_produccion=17, tipo_producto='alevines producidos', unidad_medida='unidades', aplica_a_tipo_activo='AMBOS'),
]


class _Repo:
    def __init__(self, activo, fase) -> None:
        self.activo, self.fase = activo, fase

    def obtener_por_id(self, _id, ids_fincas_permitidas=None):
        return self.activo

    def obtener_fase_activa(self, _id):
        return self.fase


class _Parametros:
    def listar_metricas_productivas(self, id_especie, tipo_activo):
        assert (id_especie, tipo_activo) == (4, 'POBLACIONAL')
        return _METRICAS


class _Ciclo:
    def metrica_habilitada_en_ciclo(self, id_ciclo, id_metrica):
        return id_ciclo == 4 and id_metrica == 17


def _ejecutar(activo, fase):
    return ListarMetricasActivoUseCase(_Repo(activo, fase), _Parametros(), _Ciclo()).execute(95)


LOTE = SimpleNamespace(id_especie=4, tipo='POBLACIONAL')


def test_marca_habilitadas_segun_el_ciclo_de_la_fase_activa() -> None:
    resultado = _ejecutar(LOTE, SimpleNamespace(id_ciclo_productiva=4))
    assert [(m.tipo_producto, h) for m, h in resultado] == [('peso vivo', False), ('alevines producidos', True)]


def test_sin_fase_activa_ninguna_esta_habilitada() -> None:
    assert [h for _, h in _ejecutar(LOTE, None)] == [False, False]


def test_activo_inexistente_404() -> None:
    with pytest.raises(NotFoundError):
        _ejecutar(None, None)

# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: valor base del umbral E12/E13 y parámetros de alertas sin BD |
"""INC-M03-168-G76: umbral_confianza_edge_ia sin cargar ya no bloquea los conflictos Edge/IA."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import (
    PARAMETROS_ALERTAS,
    ParametrosAlertasUseCase,
)
from src.configuration.domain.entities.parametro_mlops import RF57_CONFIANZA, ParametroMLOps
from src.shared.errors import ServiceUnavailableError, ValidationError
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter


def _repo(parametros):
    repo = Mock()
    repo.obtener.side_effect = lambda nombres: {n: p for n, p in parametros.items() if n in nombres}
    return repo


def test_sin_cargar_usa_el_valor_base_del_rf():
    assert ParametrosAlertasMLOpsAdapter(_repo({})).obtener_confianza_edge_ia() == Decimal("0.85")


def test_cargado_prevalece():
    p = {RF57_CONFIANZA: ParametroMLOps(RF57_CONFIANZA, 0.8, Decimal("0.70"), Decimal("0.95"))}
    assert ParametrosAlertasMLOpsAdapter(_repo(p)).obtener_confianza_edge_ia() == Decimal("0.8")


@pytest.mark.parametrize("valor", [0.5, 0.99, "alto"])
def test_cargado_invalido_sigue_fallando(valor):
    p = {RF57_CONFIANZA: ParametroMLOps(RF57_CONFIANZA, valor, Decimal("0.70"), Decimal("0.95"))}
    with pytest.raises(ServiceUnavailableError) as exc:
        ParametrosAlertasMLOpsAdapter(_repo(p)).obtener_confianza_edge_ia()
    assert exc.value.code == "PARAMETRO_CONFIGURACION_INVALIDO"


def test_consulta_indica_la_fuente_de_cada_parametro():
    p = {RF57_CONFIANZA: ParametroMLOps(RF57_CONFIANZA, 0.8, Decimal("0.70"), Decimal("0.95"))}
    por_nombre = {x.nombre: x for x in ParametrosAlertasUseCase(Mock(), _repo(p)).consultar()}
    assert set(por_nombre) == set(PARAMETROS_ALERTAS)
    assert (por_nombre[RF57_CONFIANZA].fuente, por_nombre[RF57_CONFIANZA].valor) == ("CONFIGURADO", 0.8)
    minima = por_nombre["rf57_umbral_confianza_minimo"]
    assert (minima.fuente, minima.valor, minima.valor_configurado) == ("VALOR_BASE", Decimal("0.75"), None)
    assert por_nombre["rf57_tormenta_alertas_por_minuto"].fuente == "SIN_CONFIGURAR"


@pytest.mark.parametrize("cambios", [{}, {"rf62_k": 3}, {"otro": 1}])
def test_actualizar_solo_admite_parametros_de_rf57(cambios):
    with pytest.raises(ValidationError) as exc:
        ParametrosAlertasUseCase(Mock(), _repo({})).actualizar(cambios, 1)
    assert exc.value.code == "PARAMETRO_ALERTAS_INVALIDO"

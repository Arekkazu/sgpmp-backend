# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-166-G73 RF-57 CA-2: umbral mínimo de confianza sin BD |
"""INC-M03-166-G73: umbral mínimo de confianza de IA (RF-57 CA-2) sin base de datos."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import (
    ConfigurarParametrosMLOpsUseCase,
)
from src.configuration.domain.entities.parametro_mlops import RF57_CONFIANZA_MINIMA, ParametroMLOps
from src.shared.errors import ServiceUnavailableError, ValidationError
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO


def _adaptador(parametros):
    repo = Mock()
    repo.obtener.return_value = parametros
    return ParametrosAlertasMLOpsAdapter(repo)


def test_sin_configurar_usa_el_valor_base_del_rf():
    assert _adaptador({}).obtener_confianza_minima_ia() == Decimal("0.75")


def test_configurado_se_usa():
    p = {RF57_CONFIANZA_MINIMA: ParametroMLOps(RF57_CONFIANZA_MINIMA, 0.8, Decimal(0), Decimal(1))}
    assert _adaptador(p).obtener_confianza_minima_ia() == Decimal("0.8")


@pytest.mark.parametrize("valor", ["alto", 1.5, -0.1, True])
def test_configurado_invalido_falla(valor):
    p = {RF57_CONFIANZA_MINIMA: ParametroMLOps(RF57_CONFIANZA_MINIMA, valor, Decimal(0), Decimal(1))}
    with pytest.raises(ServiceUnavailableError) as exc:
        _adaptador(p).obtener_confianza_minima_ia()
    assert exc.value.code == "PARAMETRO_CONFIGURACION_INVALIDO"


@pytest.mark.parametrize("valor", [1.2, -0.5, "0.8"])
def test_dev14_rechaza_un_umbral_fuera_de_0_1(valor):
    repo = Mock()
    repo.obtener.return_value = {}
    with pytest.raises((ValidationError, ServiceUnavailableError)):
        ConfigurarParametrosMLOpsUseCase(Mock(), repo).validar({RF57_CONFIANZA_MINIMA: valor})


def _caso_de_uso(minimo="0.75"):
    alerta_repo = Mock()
    alerta_repo.buscar_activa_duplicada.return_value = None
    alerta_repo.guardar.side_effect = lambda a: Alerta(**{**a.__dict__, "id_alerta": 1})
    parametros = Mock()
    parametros.obtener_confianza_minima_ia.return_value = Decimal(minimo)
    uc = GenararAlertaUseCase(db=Mock(), alerta_repo=alerta_repo, historico_repo=Mock(), regla_repo=Mock(),
                              parametros_port=parametros)
    return uc, alerta_repo


def _dto(probabilidad, origen="IA", tipo_ia="PREDICCION_PATOLOGIA"):
    return ProcesarEventoAlertaDTO(
        device_id=1, sensor_id=2, serial="S", tipo_variable="TEMPERATURA_AMBIENTAL", valor=Decimal("31"),
        unidad="°C", timestamp_evento=datetime.now(timezone.utc), estado_dato="LECTURA_VALIDA",
        severidad_edge="LEVE", origen_evento=origen, id_telemetria=1, tipo_alerta_ia=tipo_ia,
        severidad_ia="LEVE", probabilidad_ia=probabilidad)


@pytest.mark.parametrize("probabilidad", [Decimal("0.74"), Decimal("0.7499"), Decimal("0"), None])
def test_bajo_el_umbral_no_crea_alerta_ni_consolida(probabilidad):
    uc, repo = _caso_de_uso()
    r = uc.execute(_dto(probabilidad))
    assert r.id_alerta is None and r.motivo_descarte
    repo.buscar_activa_duplicada.assert_not_called()
    repo.guardar.assert_not_called()


def test_en_el_umbral_crea_la_prediccion():
    uc, repo = _caso_de_uso()
    r = uc.execute(_dto(Decimal("0.75")))
    assert (r.tipo_alerta, r.severidad) == ("PREDICCION_PATOLOGIA", "LEVE")
    repo.guardar.assert_called_once()


def test_el_umbral_no_aplica_a_eventos_que_no_son_prediccion_de_ia():
    uc, repo = _caso_de_uso(minimo="0.99")
    uc.execute(_dto(Decimal("0.10"), origen="EDGE", tipo_ia=None))
    repo.guardar.assert_called_once()

# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-12 | Leandro | INC-M05-357-G02 RF-74: verificar el texto del aviso, sus destinatarios y el resultado crítico. |
"""Regresión del texto visible de TC-M05-007b."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsulta
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo


@pytest.fixture
def calculo_ica():
    activo = ActivoConsulta(1627, "INDIVIDUAL", 1, "Activo", None, date(2026, 10, 1), "BOV-114-TIL")
    uc = CalcularICAUseCase(
        db=Mock(),
        resultado_repo=Mock(guardar=lambda resultado: resultado),
        consumo_read_port=Mock(),
        pesaje_port=Mock(),
        activo_port=Mock(),
        ciclo_port=Mock(),
        alerta_port=Mock(),
        notificador=Mock(),
    )
    uc.activo_port.obtener.return_value = activo
    uc.ciclo_port.obtener_abierto.return_value = None
    uc.consumo_read_port.sumar_alimento_validado.return_value = Decimal("8.4444")
    uc.pesaje_port.obtener_peso_en_o_antes.side_effect = [Decimal("10"), Decimal("11")]
    return uc, activo


@pytest.mark.parametrize(
    ("periodo", "texto_periodo", "tipo_calculo", "identificador", "nombre", "origen"),
    [
        (PeriodoEvaluacion.POR_CICLO, "en el ciclo", TipoCalculo.AUTOMATICO, "BOV-114-TIL",
         "del activo BOV-114-TIL", "EVALUACION_PERIODICA"),
        (PeriodoEvaluacion.SEMANAL, "en la semana", TipoCalculo.MANUAL, "BOV-114-TIL",
         "del activo BOV-114-TIL", "BACKEND"),
        (PeriodoEvaluacion.MENSUAL, "en el mes", TipoCalculo.REINTENTO_MANUAL, None,
         "del lote seleccionado", "BACKEND"),
    ],
)
def test_aviso_critico_usa_texto_visible_y_preserva_los_datos_del_evento(
    calculo_ica, periodo, texto_periodo, tipo_calculo, identificador, nombre, origen,
):
    uc, activo = calculo_ica
    activo.identificador = identificador
    if identificador is None:
        activo.tipo = "POBLACIONAL"
        activo.cantidad_actual = 1
    uc.notificador.a_responsables_activo.side_effect = lambda *_: uc.db.commit.assert_called_once()

    resultado = uc.execute(id_activo_biologico=1627, periodo=periodo, tipo_calculo=tipo_calculo)

    assert resultado.es_critica and resultado.ca_calculado == Decimal("8.4444")
    uc.activo_port.obtener.assert_called_once_with(1627)
    uc.notificador.a_responsables_activo.assert_called_once_with(
        1627,
        "ALERTA_CONVERSION_ALIMENTICIA",
        f"Urgencia ALTA: la conversión alimenticia {nombre} es crítica "
        f"(CA 8,4444 {texto_periodo}). Revise dieta, calidad del alimento y estado sanitario.",
        {"id_activo_biologico": 1627, "ca": "8.4444"},
    )
    alerta = uc.alerta_port.generar_alerta_critica.call_args.kwargs
    assert (alerta["id_activo_biologico"], alerta["ca_calculado"]) == (1627, Decimal("8.4444"))
    assert (alerta["periodo_evaluacion"], alerta["origen_evento"]) == (periodo.value, origen)


def test_ca_en_el_limite_no_emite_aviso(calculo_ica):
    uc, _ = calculo_ica
    uc.consumo_read_port.sumar_alimento_validado.return_value = Decimal("5")

    resultado = uc.execute(
        id_activo_biologico=1627, periodo=PeriodoEvaluacion.SEMANAL, tipo_calculo=TipoCalculo.MANUAL,
    )

    assert resultado.ca_calculado == Decimal("5") and not resultado.es_critica
    uc.alerta_port.generar_alerta_critica.assert_not_called()
    uc.notificador.a_responsables_activo.assert_not_called()


def test_calculo_sin_commit_conserva_flujo_del_cierre(calculo_ica):
    uc, _ = calculo_ica

    resultado = uc.calcular_sin_commit(
        id_activo_biologico=1627, periodo=PeriodoEvaluacion.POR_CICLO, tipo_calculo=TipoCalculo.MANUAL,
    )

    assert resultado.es_critica
    uc.alerta_port.generar_alerta_critica.assert_called_once()
    uc.db.commit.assert_not_called()
    uc.notificador.a_responsables_activo.assert_not_called()

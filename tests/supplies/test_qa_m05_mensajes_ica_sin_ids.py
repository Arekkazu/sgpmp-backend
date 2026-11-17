# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-16 | Arekkazu | QA-M05 RF-74: el aviso de activo fuera de producción nombra el activo y su estado, sin id ni «CA» |
"""Regresión: calcular el ICA de un activo que no está activo (Suministros → Eficiencia)."""

from datetime import date
from unittest.mock import Mock

import pytest

from src.shared.errors import BusinessRuleError
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsulta
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo


def test_activo_fuera_de_produccion_se_nombra_por_su_identificador():
    activo = ActivoConsulta(54, "INDIVIDUAL", 6, "BAJA", None, date(2026, 10, 1), "BOV-DEMO-02")
    uc = CalcularICAUseCase(
        db=Mock(), resultado_repo=Mock(), consumo_read_port=Mock(), pesaje_port=Mock(),
        activo_port=Mock(obtener=Mock(return_value=activo)), ciclo_port=Mock(), alerta_port=Mock(),
    )

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(id_activo_biologico=54, periodo=PeriodoEvaluacion.MENSUAL, tipo_calculo=TipoCalculo.MANUAL)

    assert exc.value.message == (
        "El activo BOV-DEMO-02 está dado de baja. El cálculo del ICA solo aplica a activos en producción."
    )


@pytest.mark.parametrize(
    ("nombre_estado", "visible"),
    [("EN_TRATAMIENTO", "en tratamiento"), ("CERRADO", "cerrado"), ("BAJA", "dado de baja"),
     (None, "fuera de producción")],
)
def test_estado_del_activo_en_palabras(nombre_estado, visible):
    assert ActivoConsulta(1, "INDIVIDUAL", 2, nombre_estado, None, None).estado_visible == visible

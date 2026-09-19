"""INC-M09-103-G28 (#294): el ORM debía declarar explícitamente la misma precisión que
RF-17 (NUMERIC(5,2)) para los valores de umbrales y niveles de alerta, en vez de un
`Numeric` sin escala que no reflejaba el esquema real.
"""
from __future__ import annotations

from src.configuration.infrastructure.models.nivel_alerta_ambiental_model import NivelAlertaAmbientalModel
from src.configuration.infrastructure.models.umbral_ambiental_model import UmbralAmbientalModel


def _precision_escala(columna) -> tuple[int, int]:
    tipo = columna.type
    return tipo.precision, tipo.scale


class TestPrecisionNumericaDeclaradaEnElOrm:
    def test_umbral_valor_min_y_max_son_numeric_5_2(self) -> None:
        assert _precision_escala(UmbralAmbientalModel.valor_min) == (5, 2)
        assert _precision_escala(UmbralAmbientalModel.valor_max) == (5, 2)

    def test_nivel_limite_inferior_y_superior_son_numeric_5_2(self) -> None:
        assert _precision_escala(NivelAlertaAmbientalModel.limite_inferior) == (5, 2)
        assert _precision_escala(NivelAlertaAmbientalModel.limite_superior) == (5, 2)

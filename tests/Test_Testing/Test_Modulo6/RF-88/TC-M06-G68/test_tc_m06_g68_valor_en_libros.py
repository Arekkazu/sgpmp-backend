"""TC-M06-G68: valor en libros de RF-88 sobre valor_por_costo.

La firma real es valor_por_costo(costo_adquisicion, vida_util_meses, meses, deterioro_acumulado).
No recibe la depreciación acumulada. Esta prueba elige vida útil y meses para que la función
calcule exactamente la depreciación de cada subcaso y entonces comprueba el valor en libros.

No abre base de datos, no llama HTTP y no persiste. La alerta de TC-M06-07 no forma parte del
resultado de esta función: ese chequeo queda aparte y no se da por cumplido.
"""
from decimal import Decimal
import inspect

from src.financial_valuation.domain.services.nic41 import valor_por_costo

COSTO = Decimal("10000000")


def test_la_firma_no_recibe_depreciacion_acumulada():
    parametros = list(inspect.signature(valor_por_costo).parameters)
    assert parametros == ["costo_adquisicion", "vida_util_meses", "meses", "deterioro_acumulado"]


def test_tc_m06_05_calculo_ordinario():
    """10.000.000 × 2 / 10 = 2.000.000; menos deterioro 1.000.000 = 7.000.000."""
    valor = valor_por_costo(COSTO, 10, 2, Decimal("1000000"))
    assert valor.costo_adquisicion == COSTO
    assert valor.depreciacion_acumulada == Decimal("2000000")
    assert valor.deterioro_acumulado == Decimal("1000000")
    assert valor.valor_contable == Decimal("7000000")


def test_tc_m06_06_depreciacion_igual_al_costo():
    """12 de 12 meses agotan el costo. El deterioro es 0 y el valor en libros queda en 0."""
    valor = valor_por_costo(COSTO, 12, 12, Decimal("0"))
    assert valor.depreciacion_acumulada == COSTO
    assert valor.deterioro_acumulado == Decimal("0")
    assert valor.valor_contable == Decimal("0")


def test_tc_m06_07_el_resultado_negativo_queda_en_cero():
    """10.000.000 × 7 / 10 = 7.000.000; más deterioro 5.000.000 da −2.000.000 y se guarda 0."""
    valor = valor_por_costo(COSTO, 10, 7, Decimal("5000000"))
    assert valor.depreciacion_acumulada == Decimal("7000000")
    assert valor.deterioro_acumulado == Decimal("5000000")
    assert valor.costo_adquisicion - valor.depreciacion_acumulada - valor.deterioro_acumulado == Decimal("-2000000")
    assert valor.valor_contable == Decimal("0")


def test_tc_m06_07_la_alerta_especifica_no_se_produce():
    """El piso en cero no es la alerta. totalmente_depreciado tampoco lo es."""
    valor = valor_por_costo(COSTO, 10, 7, Decimal("5000000"))
    assert valor.valor_contable == Decimal("0")
    campos = set(valor.__dataclass_fields__)
    assert "alerta" not in campos
    assert getattr(valor, "alerta", None) is not None, (
        "valor_por_costo devolvio valor en libros 0 sin alerta. "
        "ValorPorCosto solo trae costo, depreciacion, deterioro y valor_contable. "
        "totalmente_depreciado es un booleano. "
        "El texto aviso de RegistrarDeterioroUseCase y el evento DETERIORO_REGISTRADO "
        "no son la alerta de este subcaso."
    )

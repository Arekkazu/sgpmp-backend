# | Fecha      | Nombre         | Que se hizo                                                        |
# |------------|----------------|--------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-303-G04 RF-82: 5 decimales se rechazan, no se redondean     |
"""INC-M06-303-G04 (#990): un valor con 5 decimales se rechaza en vez de redondearse.

Las columnas destino son ``numeric(18,4)`` (``modulo2.activos_biologicos.costo_adquisicion``
y ``modulo6.calculos_valor_razonable.costo_*``): sin límite en el DTO PostgreSQL redondeaba
en silencio. Con 4 decimales el valor se acepta exacto.
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.financial_valuation.infrastructure.dto.m06_dto import ConfirmarReconocimientoDTO, CostosManualesDTO
from src.shared.error_handlers import _mensaje_legible

_ACTIVO = {
    "tipo_activo": "POBLACIONAL", "id_especie": 1, "fecha_inicio_ciclo": "2026-01-01",
    "origen_financiero": "compra", "soporte_documental": "Factura 123", "id_infraestructura": 1,
    "cantidad_inicial": 10,
}


def _error(exc: pytest.ExceptionInfo) -> dict:
    return exc.value.errors()[0]


def test_costo_adquisicion_con_cinco_decimales_se_rechaza():
    with pytest.raises(ValidationError) as exc:
        RegistrarActivoBiologicoDTO(**_ACTIVO, costo_adquisicion="1000.00005")
    assert _error(exc)["type"] == "decimal_max_places"
    assert _error(exc)["loc"] == ("costo_adquisicion",)


def test_costo_adquisicion_con_cuatro_decimales_se_guarda_exacto():
    dto = RegistrarActivoBiologicoDTO(**_ACTIVO, costo_adquisicion="1000.0001")
    assert dto.costo_adquisicion == Decimal("1000.0001")


@pytest.mark.parametrize("campo", ["transporte", "comisiones", "impuestos", "otros"])
def test_costo_manual_con_cinco_decimales_se_rechaza(campo):
    with pytest.raises(ValidationError) as exc:
        CostosManualesDTO(**{campo: "100.00005"})
    assert _error(exc)["type"] == "decimal_max_places"


def test_costo_manual_con_cuatro_decimales_se_acepta():
    dto = ConfirmarReconocimientoDTO(costos_manuales={"transporte": "100.0001"},
                                     justificacion="Factura de transporte 001 del proveedor")
    assert dto.costos_manuales.transporte == Decimal("100.0001")


def test_mensaje_visible_en_espanol():
    with pytest.raises(ValidationError) as exc:
        CostosManualesDTO(transporte="100.00005")
    assert _mensaje_legible(_error(exc)) == "El valor admite como máximo 4 decimales."

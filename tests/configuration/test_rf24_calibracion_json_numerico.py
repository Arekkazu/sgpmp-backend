"""#251 (QA M09, TC-DIS-66): las calibraciones viajan con números en el JSON.

Pydantic v2 serializa ``Decimal`` como texto ("10.0000"); el frontend declara
estos campos como ``number`` y su vista hacía aritmética sobre ellos, así que
la pantalla de calibración de un sensor con historial quedaba en blanco.
"""
import datetime
import json
from decimal import Decimal

from src.configuration.infrastructure.schema.calibracion_schema import (
    CalibracionResponse,
    RangoCalibracionResponse,
)


def _calibracion() -> CalibracionResponse:
    return CalibracionResponse(
        id_calibracion=9,
        id_dispositivo_iot=1,
        id_sensor=3,
        valor_referencia=Decimal("10.0000"),
        ganancia=Decimal("1.0000"),
        offset=Decimal("10.0000"),
        fecha_calibracion=datetime.datetime(2026, 10, 6, 12, 0),
        id_usuario=126,
        observaciones=None,
        modo_calibracion="SENSOR",
    )


def test_calibracion_serializa_valores_como_numero_json():
    cuerpo = json.loads(_calibracion().model_dump_json())

    for campo in ("valor_referencia", "ganancia", "offset"):
        assert isinstance(cuerpo[campo], (int, float)), campo
    assert cuerpo["valor_referencia"] == 10.0


def test_rango_de_calibracion_serializa_limites_como_numero_json():
    cuerpo = json.loads(
        RangoCalibracionResponse(categoria="PH", valor_min=Decimal("0"), valor_max=Decimal("14")).model_dump_json()
    )

    assert cuerpo == {"categoria": "PH", "valor_min": 0.0, "valor_max": 14.0}


def test_en_python_se_conserva_decimal():
    # Solo cambia la salida JSON: el resto del backend sigue operando con Decimal.
    assert isinstance(_calibracion().model_dump()["valor_referencia"], Decimal)

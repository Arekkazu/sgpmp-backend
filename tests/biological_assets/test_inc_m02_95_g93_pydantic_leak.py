"""INC-M02-95-G93 — GET /{id_activo}/datos-consolidados exponía detalles
internos de Pydantic en el 400 de `fecha_inicio > fecha_fin` (nombre del DTO,
`type=value_error`, `input_value`, URL de `errors.pydantic.dev`).

Causa raíz: el router capturaba `except ValueError` antes que
`except _PydanticValidationError` — como `pydantic.ValidationError` es
subclase de `ValueError`, la rama específica que limpiaba el mensaje
(`errors()[0]['msg']`) nunca se ejecutaba (confirmado por Pyright:
`reportUnusedExcept`) y el cliente recibía `str(exc)`, el volcado completo de
Pydantic. El mismo patrón estaba copiado en 6 endpoints de este router
(`listar_activos`, `consultar_bitacora`, `consultar_historial`,
`consultar_indicadores`, `consultar_datos_consolidados` — el nombrado en el
issue — y una variante de un solo `except` combinado); se corrigieron todos
con un único helper (`_error_parametros_invalidos`).
"""
from __future__ import annotations

from datetime import date

import pytest

from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.biological_assets.infrastructure.routers.activo_biologico_router import _error_parametros_invalidos
from src.shared.errors import ValidationError as DomainValidationError

_FRAGMENTOS_INTERNOS_PYDANTIC = (
    "DatosConsolidadosDTO",
    "value_error",
    "input_value",
    "errors.pydantic.dev",
    "1 validation error",
)


def test_rango_fechas_invalido_no_expone_detalles_de_pydantic() -> None:
    with pytest.raises(ValueError) as exc_info:
        DatosConsolidadosDTO(fecha_inicio=date(2026, 8, 31), fecha_fin=date(2026, 6, 1))

    error = _error_parametros_invalidos(exc_info.value)

    assert isinstance(error, DomainValidationError)
    assert error.code == "PARAMETROS_INVALIDOS"
    for fragmento in _FRAGMENTOS_INTERNOS_PYDANTIC:
        assert fragmento not in error.message
    assert "no puede ser posterior" in error.message


def test_tipo_dato_invalido_no_expone_detalles_de_pydantic() -> None:
    with pytest.raises(ValueError) as exc_info:
        DatosConsolidadosDTO(tipo_dato="no-existe")

    error = _error_parametros_invalidos(exc_info.value)

    assert error.code == "PARAMETROS_INVALIDOS"
    for fragmento in _FRAGMENTOS_INTERNOS_PYDANTIC:
        assert fragmento not in error.message
    assert "Tipo de dato inválido" in error.message


def test_valueerror_plano_conserva_su_mensaje() -> None:
    """Un ValueError que no viene de Pydantic (ej. date.fromisoformat en el
    router, antes de construir el DTO) no debe pasar por el parseo de
    `errors()` — no es una instancia de `pydantic.ValidationError`."""
    error = _error_parametros_invalidos(ValueError("Invalid isoformat string: 'no-es-fecha'"))

    assert error.code == "PARAMETROS_INVALIDOS"
    assert error.message == "Invalid isoformat string: 'no-es-fecha'"

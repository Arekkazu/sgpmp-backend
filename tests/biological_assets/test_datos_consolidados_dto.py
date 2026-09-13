"""INC-M02-91-G93 (RF-50, TC-M02-156-B): datos-consolidados no rechazaba un
rango de fechas íntegramente futuro.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO


def test_rechaza_fecha_inicio_futura() -> None:
    manana = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        DatosConsolidadosDTO(fecha_inicio=manana, fecha_fin=manana + timedelta(days=1))


def test_acepta_fecha_inicio_hoy() -> None:
    hoy = date.today()
    dto = DatosConsolidadosDTO(fecha_inicio=hoy, fecha_fin=hoy)
    assert dto.fecha_inicio == hoy


def test_acepta_rango_pasado() -> None:
    ayer = date.today() - timedelta(days=1)
    dto = DatosConsolidadosDTO(fecha_inicio=ayer, fecha_fin=date.today())
    assert dto.fecha_fin == date.today()


def test_acepta_sin_fechas() -> None:
    dto = DatosConsolidadosDTO()
    assert dto.fecha_inicio is None

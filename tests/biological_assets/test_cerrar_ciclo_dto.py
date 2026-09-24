"""RF-38 (INC-M02-29-g36 / #411): `fecha_cierre` no puede ser futura, pero la
referencia de "futuro" debe ser la fecha UTC -- la misma que usa
`CerrarCicloUseCase` para persistir `fecha_cierre_dt` -- no `date.today()`
(fecha local del proceso). En un servidor cuya zona horaria va detrás de
UTC, un `fecha_cierre` = "hoy" en UTC podía rechazarse aquí como futura
porque localmente todavía era "ayer".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO


def test_acepta_fecha_de_hoy_en_utc() -> None:
    hoy_utc = datetime.now(timezone.utc).date()
    dto = CerrarCicloDTO(fecha_cierre=hoy_utc, motivo_cierre='venta')
    assert dto.fecha_cierre == hoy_utc


def test_rechaza_fecha_futura_en_utc() -> None:
    # +2 días, no +1: si la zona local va detrás de UTC, "mañana local"
    # puede seguir siendo "hoy" en UTC y no sería futura.
    pasado_manana_utc = datetime.now(timezone.utc).date() + timedelta(days=2)
    with pytest.raises(ValidationError):
        CerrarCicloDTO(fecha_cierre=pasado_manana_utc, motivo_cierre='venta')

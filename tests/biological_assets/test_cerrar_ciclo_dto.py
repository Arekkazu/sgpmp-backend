# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""RF-38: `fecha_cierre` no puede ser futura respecto al día en Colombia --
ni el del proceso (#411) ni el UTC, que desde las 19:00 hora local ya va en
el día siguiente (ver `src/shared/fechas.py`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

import src.shared.fechas as fechas
from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO


@pytest.fixture(autouse=True)
def noche_en_colombia(monkeypatch, en_colombia) -> None:
    # 2026-10-11 22:25 en Colombia == 2026-10-12 03:25 UTC
    monkeypatch.setattr(
        fechas, '_ahora', lambda: datetime(2026, 10, 12, 3, 25, tzinfo=timezone.utc).astimezone(en_colombia),
    )


def test_acepta_hoy_en_colombia() -> None:
    dto = CerrarCicloDTO(fecha_cierre=date(2026, 10, 11), motivo_cierre='venta')
    assert dto.fecha_cierre == date(2026, 10, 11)


def test_rechaza_manana_en_colombia_aunque_en_utc_ya_sea_hoy() -> None:
    with pytest.raises(ValidationError):
        CerrarCicloDTO(fecha_cierre=date(2026, 10, 12), motivo_cierre='venta')

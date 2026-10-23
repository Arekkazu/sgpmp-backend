# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Aislamiento compartido por toda la suite."""
from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

import src.shared.fechas as fechas
from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora


@pytest.fixture(autouse=True)
def _buffer_auditoria_m02_aislado(tmp_path, monkeypatch) -> None:
    """RF-52 E1/E3: el buffer de auditoría de M02 y el control de carga son estado
    de proceso. Con el `logs/` real, el fallo simulado de una prueba se
    "recuperaría" dentro del repositorio falso de la siguiente; con un solo
    ControlCarga, las ráfagas de una prueba contarían para la siguiente.
    """
    monkeypatch.setattr(bitacora, '_DIR', tmp_path / 'logs')
    monkeypatch.setattr(bitacora, '_control', bitacora.ControlCarga())


@pytest.fixture
def en_colombia():
    """El request trae ``X-Zona-Horaria: America/Bogota`` (sin ella el día es el de UTC)."""
    token = fechas.establecer_zona_usuario('America/Bogota')
    yield ZoneInfo('America/Bogota')
    fechas._zona.reset(token)

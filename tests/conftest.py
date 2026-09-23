"""Aislamiento compartido por toda la suite."""
from __future__ import annotations

import pytest

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

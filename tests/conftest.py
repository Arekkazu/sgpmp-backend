"""Aislamiento compartido por toda la suite."""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora


@pytest.fixture(autouse=True)
def _buffer_auditoria_m02_aislado(tmp_path, monkeypatch) -> None:
    """RF-52 E1: el buffer de auditoría de M02 se recupera en la siguiente escritura
    exitosa. Si fuera el `logs/` real, el fallo simulado de una prueba se
    "recuperaría" dentro del repositorio falso de la siguiente.
    """
    monkeypatch.setattr(bitacora, '_BUFFER', tmp_path / 'logs' / 'audit_buffer_M02.jsonl')
    monkeypatch.setattr(bitacora, '_LOCK', tmp_path / 'logs' / 'audit_buffer_M02.lock')

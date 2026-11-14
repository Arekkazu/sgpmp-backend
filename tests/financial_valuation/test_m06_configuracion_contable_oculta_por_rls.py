# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | M06 RF-82: 403 si la RLS oculta la configuración contable (antes 500) |
"""Un rol sin lectura de ``configuracion_contable`` (el Auditor) recibía 500 en las propuestas de
reconocimiento: la RLS ocultaba la fila y el repositorio hacía ``ConfiguracionContable(**None)``."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.financial_valuation.infrastructure.repositories.configuracion_contable_repository import (
    SqlAlchemyConfiguracionContableRepository,
)
from src.shared.errors import AuthorizationError


def test_fila_oculta_por_rls_responde_403_sin_codigos_internos():
    db = MagicMock()
    db.execute.return_value.first.return_value = None  # lo que devuelve la RLS a un rol sin permiso

    with pytest.raises(AuthorizationError) as exc:
        SqlAlchemyConfiguracionContableRepository(db).obtener()

    assert exc.value.status_code == 403
    assert "configuracion_contable" not in exc.value.message

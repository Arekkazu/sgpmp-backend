# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-46 RF-15: proceso crítico activo → 422, no 423 |
"""DEV-46 (RF-15 C-10): desactivar una especie con proceso crítico activo responde 422."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.especies.desactivar_especie_use_case import DesactivarEspecieUseCase
from src.shared.errors import BusinessRuleError


def test_proceso_critico_activo_responde_422_sin_tocar_la_especie():
    especie = Mock(es_activo=True)
    repo = Mock()
    repo.obtener_por_id.return_value = especie
    proceso = Mock()
    proceso.tiene_proceso_activo.return_value = True
    db = Mock()
    uc = DesactivarEspecieUseCase(db=db, especies_repo=repo, auditoria_repo=Mock(), proceso_critico_port=proceso)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(7, SimpleNamespace(id_usuario=1, id_rol=1))

    assert exc.value.status_code == 422
    assert exc.value.code == "ESPECIE_CON_PROCESO_ACTIVO"
    especie.desactivar.assert_not_called()
    repo.actualizar.assert_not_called()
    db.commit.assert_not_called()

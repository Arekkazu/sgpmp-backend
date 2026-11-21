# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M04-01 RF-69: las pruebas de transiciones simulan un artefacto firmado |
"""Las pruebas de M04 arman versiones sin archivo en disco ni firma (SEG-M04-01). Salvo las marcadas
``firma_real``, que prueban justamente esa verificación, se da por íntegro y firmado el artefacto."""
import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo


@pytest.fixture(autouse=True)
def _artefacto_firmado(request, monkeypatch):
    if request.node.get_closest_marker("firma_real"):
        return
    monkeypatch.setattr(VersionModelo, "exigir_artefacto_integro", lambda self, sha, clave: None)
    monkeypatch.setattr(RegistrarVersionModeloUseCase, "_verificar_firma", lambda self, sha, firma, proceso: "f" * 64)

# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: Consultar la configuración operativa activa (GET RF-18)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal
from src.configuration.domain.repositories.configuracion_global_repository import ConfiguracionGlobalRepository


class ConsultarConfiguracionUseCase:
    """Devuelve la configuración operativa activa, o ``None`` si aún no se creó."""

    def __init__(self, config_repo: ConfiguracionGlobalRepository) -> None:
        self.config_repo = config_repo

    def execute(self) -> Optional[ConfiguracionGlobal]:
        """Devuelve la configuración global activa, o ``None``."""
        return self.config_repo.obtener_activo()

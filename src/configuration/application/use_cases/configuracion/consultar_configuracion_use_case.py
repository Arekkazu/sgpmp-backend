"""Caso de uso: Consultar la configuración operativa activa (GET RF-18)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal
from src.configuration.domain.repositories.configuracion_global_repository import ConfiguracionGlobalRepository


class ConsultarConfiguracionUseCase:

    def __init__(self, config_repo: ConfiguracionGlobalRepository) -> None:
        self.config_repo = config_repo

    def execute(self) -> Optional[ConfiguracionGlobal]:
        return self.config_repo.obtener_activo()

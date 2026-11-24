# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso de consulta de la configuración del motor de IA."""
from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.shared.errors import NotFoundError


class ConsultarMotorUseCase:
    """Consulta la configuración del motor de IA."""
    def __init__(self, *, repo: ConfiguracionMotorIARepository) -> None:
        self._repo = repo

    def listar(self) -> list[ConfiguracionMotorIA]:
        """Lista las configuraciones de todos los tipos de modelo."""
        return self._repo.listar()

    def obtener_por_tipo(self, tipo_modelo: str) -> ConfiguracionMotorIA:
        """Devuelve la configuración del tipo de modelo.

        Raises:
            NotFoundError: Si no hay configuración.
        """
        entidad = self._repo.obtener_por_tipo(tipo_modelo)
        if entidad is None:
            raise NotFoundError(
                code="CONFIGURACION_MOTOR_NO_ENCONTRADA",
                message=f"No existe configuración para el tipo de modelo '{tipo_modelo}'.",
            )
        return entidad

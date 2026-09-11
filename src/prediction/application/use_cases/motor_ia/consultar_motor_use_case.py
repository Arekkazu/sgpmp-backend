from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.shared.errors import NotFoundError


class ConsultarMotorUseCase:
    def __init__(self, *, repo: ConfiguracionMotorIARepository) -> None:
        self._repo = repo

    def listar(self) -> list[ConfiguracionMotorIA]:
        return self._repo.listar()

    def obtener_por_tipo(self, tipo_modelo: str) -> ConfiguracionMotorIA:
        entidad = self._repo.obtener_por_tipo(tipo_modelo)
        if entidad is None:
            raise NotFoundError(
                code="CONFIGURACION_MOTOR_NO_ENCONTRADA",
                message=f"No existe configuración para el tipo de modelo '{tipo_modelo}'.",
            )
        return entidad

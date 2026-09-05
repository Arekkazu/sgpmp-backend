from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA


class ConfiguracionMotorIARepository(ABC):
    @abstractmethod
    def obtener_por_tipo(self, tipo_modelo: str) -> Optional[ConfiguracionMotorIA]: ...

    @abstractmethod
    def listar(self) -> list[ConfiguracionMotorIA]: ...

    @abstractmethod
    def guardar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA: ...

    @abstractmethod
    def actualizar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA: ...

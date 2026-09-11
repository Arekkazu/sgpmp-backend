from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.alerta import ReglaAlerta


class ReglaAlertaRepository(ABC):

    @abstractmethod
    def obtener_reglas_activas_por_variable(self, tipo_variable: str) -> list[ReglaAlerta]: ...

    @abstractmethod
    def obtener_reglas_compuestas_activas(self) -> list[ReglaAlerta]: ...

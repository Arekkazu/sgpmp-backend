# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: crear, actualizar y listar reglas de alerta |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.alerta import ReglaAlerta


class ReglaAlertaRepository(ABC):

    @abstractmethod
    def obtener_reglas_activas_por_variable(self, tipo_variable: str) -> list[ReglaAlerta]: ...

    @abstractmethod
    def obtener_reglas_compuestas_activas(self) -> list[ReglaAlerta]: ...

    @abstractmethod
    def obtener_por_id(self, id_regla_alertas: int, *, bloquear: bool = False) -> Optional[ReglaAlerta]: ...

    @abstractmethod
    def listar(
        self,
        *,
        tipo_sensor: Optional[str] = None,
        es_activa: Optional[bool] = None,
        es_regla_compuesta: Optional[bool] = None,
    ) -> list[ReglaAlerta]: ...

    @abstractmethod
    def crear(self, regla: ReglaAlerta) -> ReglaAlerta: ...

    @abstractmethod
    def actualizar(self, regla: ReglaAlerta) -> ReglaAlerta: ...

# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: crear, actualizar y listar reglas de alerta |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio del catálogo de reglas de alerta (RF-55).

Expone las reglas simples activas por variable, las compuestas activas y el
CRUD de configuración. La aplicación solo conoce esta interfaz.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.alerta import ReglaAlerta


class ReglaAlertaRepository(ABC):
    """Contrato de consulta y mantenimiento de reglas de alerta."""

    @abstractmethod
    def obtener_reglas_activas_por_variable(self, tipo_variable: str) -> list[ReglaAlerta]:
        """Devuelve las reglas simples activas que aplican a la variable indicada."""
        ...

    @abstractmethod
    def obtener_reglas_compuestas_activas(self) -> list[ReglaAlerta]:
        """Devuelve todas las reglas compuestas activas."""
        ...

    @abstractmethod
    def obtener_por_id(self, id_regla_alertas: int, *, bloquear: bool = False) -> Optional[ReglaAlerta]:
        """Busca una regla por id; ``bloquear`` toma el registro para edición."""
        ...

    @abstractmethod
    def listar(
        self,
        *,
        tipo_sensor: Optional[str] = None,
        es_activa: Optional[bool] = None,
        es_regla_compuesta: Optional[bool] = None,
    ) -> list[ReglaAlerta]:
        """Lista reglas filtrando por sensor, actividad y tipo (simple/compuesta)."""
        ...

    @abstractmethod
    def crear(self, regla: ReglaAlerta) -> ReglaAlerta:
        """Crea una regla y devuelve la entidad con su identificador."""
        ...

    @abstractmethod
    def actualizar(self, regla: ReglaAlerta) -> ReglaAlerta:
        """Actualiza una regla existente y devuelve la entidad resultante."""
        ...

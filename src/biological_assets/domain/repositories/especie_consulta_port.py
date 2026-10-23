# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
"""Puerto de lectura de especies del catálogo de M09."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EspecieConsulta:
    """Especie de M09 con su estado de activación."""
    id_especie: int
    nombre: str
    es_activo: bool
    # RFC-014: esperanza de vida en días (RF-15); None = la especie no la define.
    esperanza_vida_dias: Optional[int] = None


class EspecieConsultaPort(ABC):
    """Consulta a M09 de especies activas."""

    @abstractmethod
    def obtener_activa(self, id_especie: int) -> Optional[EspecieConsulta]:
        """Retorna la especie si existe y está activa, None en caso contrario."""

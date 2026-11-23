# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: solicitudes de correctivo de variaciones |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de las solicitudes de correctivo de variaciones de valor razonable (RF-86 restricción 5, CA-13)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.entities.valoracion import SolicitudCorrectivo, VariacionRegistro


class CorrectivoVariacionRepository(ABC):
    """Puerto de solicitudes de corrección de variaciones."""
    @abstractmethod
    def variacion(self, id_variacion: int) -> Optional[VariacionRegistro]:
        """La variación con su referencia al registro que corrige (``id_variacion_corregida``), si la tiene."""

    @abstractmethod
    def solicitud_vigente(self, id_variacion: int) -> Optional[SolicitudCorrectivo]:
        """La solicitud PENDIENTE o APROBADA de la variación (hay a lo sumo una)."""

    @abstractmethod
    def obtener(self, id_solicitud: int, bloquear: bool = False) -> Optional[SolicitudCorrectivo]:
        """Devuelve la solicitud, opcionalmente bloqueada, o ``None``."""
        ...

    @abstractmethod
    def agregar(self, id_variacion: int, motivo: str, id_usuario: int) -> int:
        """Registra la solicitud y devuelve su id."""
        ...

    @abstractmethod
    def aprobar(self, id_solicitud: int, id_usuario: int, id_variacion_correctiva: int) -> None:
        """Marca la solicitud como aprobada con su variación correctiva."""
        ...

    @abstractmethod
    def rechazar(self, id_solicitud: int, id_usuario: int, motivo_rechazo: str) -> None:
        """Marca la solicitud como rechazada con su motivo."""
        ...

    @abstractmethod
    def listar(self, filtros: dict) -> list[dict]:
        """Solicitudes con su variación y su activo; filtros por estado, período y activo (AND)."""

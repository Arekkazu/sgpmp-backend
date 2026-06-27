"""Puerto de auditoría de plantillas de configuración (capa de dominio).

Registro append-only: solo admite inserción. Solo operación 'CREATE'
ya que las plantillas son inmutables.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaPlantillaRepository(ABC):
    """Contrato para registrar operaciones sobre plantillas de configuración."""

    @abstractmethod
    def registrar(
        self,
        *,
        id_plantilla: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría append-only.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            id_plantilla: Plantilla sobre la que se realizó la operación.
            id_usuario: Usuario que ejecutó la operación.
            tipo_operacion: Solo ``CREATE``.
            valores_nuevos: Snapshot del estado tras la operación.
            valores_anteriores: Siempre ``None`` para plantillas (inmutables).
        """
        raise NotImplementedError

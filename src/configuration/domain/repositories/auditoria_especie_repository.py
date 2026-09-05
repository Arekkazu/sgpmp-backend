"""Puerto de auditoría del catálogo de especies (capa de dominio).

Registro append-only: solo admite inserción. Nunca se actualiza ni elimina
un registro de auditoría existente.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaEspecieRepository(ABC):
    """Contrato para registrar operaciones sobre el catálogo de especies."""

    @abstractmethod
    def registrar(
        self,
        *,
        id_especie: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría append-only.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            id_especie: Especie sobre la que se realizó la operación.
            id_usuario: Usuario que ejecutó la operación.
            tipo_operacion: ``CREATE``, ``UPDATE`` o ``DEACTIVATE``.
            valores_nuevos: Snapshot del estado tras la operación.
            valores_anteriores: Snapshot del estado previo. ``None`` en CREATE.
        """
        raise NotImplementedError

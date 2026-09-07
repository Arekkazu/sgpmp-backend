"""Puerto de auditoría de plantillas de configuración (capa de dominio).

Registro append-only: solo admite inserción. Solo operación 'CREATE'
ya que las plantillas son inmutables.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.configuration.domain.entities.auditoria_plantilla import AuditoriaPlantilla


class AuditoriaPlantillaRepository(ABC):
    """Contrato para registrar y consultar operaciones sobre plantillas."""

    @abstractmethod
    def listar_todas(self) -> list[AuditoriaPlantilla]:
        """Retorna todo el historial de auditoría (creación y versionado).

        CU-07 Flujo D (RF-30): sin esto, no hay forma de consultar quién creó
        o versionó una plantilla y cuándo, aunque el registro ya se guarde en
        cada operación de escritura.
        """
        raise NotImplementedError

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

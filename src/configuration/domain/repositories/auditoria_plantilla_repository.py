"""Puerto de auditoría de plantillas de configuración (capa de dominio).

Registro append-only: solo admite inserción. Cubre creación, versionado,
consulta y aplicación de plantillas, exitosas o fallidas (INC-M09-01-109).
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
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        id_plantilla: Optional[int] = None,
        resultado: str = "EXITOSO",
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría append-only.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso (o el
        helper ``registrar_intento_fallido`` para el camino de fallo).

        Args:
            id_usuario: Usuario que ejecutó la operación.
            tipo_operacion: ``CREATE``, ``READ`` o ``APPLY``.
            valores_nuevos: Snapshot del estado tras la operación, o detalle
                del error si ``resultado == "FALLIDO"``.
            id_plantilla: Plantilla sobre la que se realizó la operación.
                ``None`` si el intento falló antes de tener un id (ej. creación
                rechazada por nombre duplicado).
            resultado: ``EXITOSO`` o ``FALLIDO``.
            valores_anteriores: Estado previo, cuando aplica (ej. versionado).
        """
        raise NotImplementedError

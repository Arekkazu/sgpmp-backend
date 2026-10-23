# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: SUPERADO y entrega a M06           |
"""Puerto del repositorio de provisiones consolidadas NIC-41 (RF-79, CU-05).

Expresado en términos de dominio: recibe y devuelve ``ProvisionNic41``.
Inmutable una vez persistida — no expone ningún método de actualización;
correcciones se modelan como filas nuevas (``guardar`` de nuevo, con
``version_reporte``/``id_reporte_anterior`` ya resueltos por el use case).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.supplies.domain.entities.provision_nic41 import ProvisionNic41


class ProvisionNic41Repository(ABC):
    """Contrato de persistencia de reportes consolidados de provisión NIC-41."""

    @abstractmethod
    def guardar(self, provision: ProvisionNic41) -> ProvisionNic41:
        """Persiste un reporte consolidado nuevo (nunca actualiza uno existente)."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_provision: int) -> Optional[ProvisionNic41]:
        """Devuelve un reporte por id, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_ultima_version(self, id_gestion_fases: int) -> Optional[ProvisionNic41]:
        """Devuelve la versión más reciente del reporte consolidado de una instancia de ciclo."""
        raise NotImplementedError

    @abstractmethod
    def listar_versiones(self, id_gestion_fases: int) -> list[ProvisionNic41]:
        """Lista todas las versiones (cadena de correcciones) de una instancia de ciclo."""
        raise NotImplementedError

    @abstractmethod
    def marcar_superado(self, id_provision: int) -> None:
        """La versión anterior queda SUPERADO al generarse una corrección (RF-79 E4)."""
        raise NotImplementedError

    @abstractmethod
    def marcar_entregado(self, id_provision: int, fecha: datetime) -> None:
        """M06 confirmó la recepción del reporte consolidado (RF-79 Fase 3)."""
        raise NotImplementedError

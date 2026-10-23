# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69: avisos de carga externa y rechazo       |
# | 2026-10-23 | Arekkazu     | DEV-37 RF-73 E8: aviso al Administrador por el respaldo activado |
"""Puerto de avisos del ciclo de vida de versiones de modelo (RF-69 E1b y E3, DEV-48).

Los avisos son *best-effort*: se envían después del commit y una implementación
nunca debe propagar un fallo de entrega, porque el dato de negocio (o el rechazo
del intento externo) ya quedó resuelto.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.version_modelo import VersionModelo


class AvisoVersionModeloPort(ABC):
    @abstractmethod
    def avisar_carga_externa(self, *, id_proceso_rf71: str, motivo: str) -> None:
        """RF-69 E1b: avisa al Administrador de un intento de carga de un modelo externo."""
        ...

    @abstractmethod
    def avisar_version_rechazada(self, version: VersionModelo) -> None:
        """RF-69 E3: avisa al Veterinario que una versión quedó RECHAZADO por métricas."""
        ...


class AvisoFallbackAuditoriaPort(ABC):
    @abstractmethod
    def avisar_fallback_activado(self, *, inicio_contingencia: str | None, eventos: int) -> None:
        """RF-73 E8: avisa al Administrador que la auditoría de M04 usó el respaldo local.
        Best-effort: nunca propaga."""
        ...

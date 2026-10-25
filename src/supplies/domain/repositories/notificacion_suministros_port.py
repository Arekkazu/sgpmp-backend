# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74/77/79/81: notificaciones internas   |
"""Puerto de las notificaciones internas de M05 (bandeja RF-14).

Lo usan: RF-74 (CA crítica al Productor y Veterinario del activo; batch
interrumpido), RF-77 (reporte asíncrono listo o fallido), RF-79 (provisión
pendiente al administrador; consolidado incompleto al contador) y RF-81
(resultado asíncrono listo). Best-effort: se llama después del ``commit`` y un
fallo nunca afecta la operación ya confirmada.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificacionSuministrosPort(ABC):
    @abstractmethod
    def a_usuarios(self, ids_usuarios: list[int], tipo_evento: str, mensaje: str, detalle: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def a_permiso(self, id_recurso: int, id_accion: int, tipo_evento: str, mensaje: str, detalle: dict) -> None:
        """A quienes tengan ese permiso RBAC activo (los roles son dinámicos)."""
        raise NotImplementedError

    @abstractmethod
    def a_responsables_activo(self, id_activo: int, tipo_evento: str, mensaje: str, detalle: dict) -> None:
        """Al Productor dueño del activo y a los Veterinarios de su finca."""
        raise NotImplementedError

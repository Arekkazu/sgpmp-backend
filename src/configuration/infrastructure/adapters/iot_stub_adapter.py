# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Stub del adaptador IoT — no hace nada hasta que el módulo de monitoreo esté disponible."""
from __future__ import annotations

from src.configuration.domain.repositories.iot_notificacion_port import IotNotificacionPort


class IotStubAdapter(IotNotificacionPort):
    """Stub que no notifica la configuración a los dispositivos."""

    def notificar_configuracion(self, *, frecuencia_muestreo: int, heartbeat: int) -> None:
        """Notifica la configuración operativa activa al módulo de monitoreo IoT."""
        pass

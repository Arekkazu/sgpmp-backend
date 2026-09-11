"""Stub del adaptador IoT — no hace nada hasta que el módulo de monitoreo esté disponible."""
from __future__ import annotations

from src.configuration.domain.repositories.iot_notificacion_port import IotNotificacionPort


class IotStubAdapter(IotNotificacionPort):

    def notificar_configuracion(self, *, frecuencia_muestreo: int, heartbeat: int) -> None:
        pass

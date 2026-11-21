# | Fecha      | Nombre         | Que se hizo |
# |------------|----------------|-------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-352-G18 RF-76: el fin de retiro avisa también al Veterinario |
"""Puerto de notificaciones del período de retiro de un medicamento (RF-76 pasos 9 y 13).

Declara la necesidad de avisar al Productor (dueño del activo) y, cuando aplica,
al Veterinario responsable, sobre el inicio y el fin del período de retiro. La
implementación concreta vive en ``infrastructure/adapters`` y es responsable de
resolver destinatarios y despachar el envío de forma *best-effort*: un fallo de
notificación nunca debe interrumpir el flujo de negocio que ya persistió sus
datos (registro del medicamento o reversión del estado del activo).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class NotificacionMedicamentoPort(ABC):
    """Contrato de notificación del ciclo de vida del período de retiro (RF-76)."""

    @abstractmethod
    def notificar_inicio_retiro(
        self,
        id_activo: int,
        id_usuario_veterinario: Optional[int],
        nombre_medicamento: str,
        fecha_fin_retiro: date,
    ) -> None:
        """Avisa al Productor (y al Veterinario si se conoce su usuario) que inició el retiro."""
        raise NotImplementedError

    @abstractmethod
    def notificar_fin_retiro(
        self, id_activo: int, fecha_fin_retiro: date, id_usuario_veterinario: Optional[int] = None
    ) -> None:
        """RF-76 paso 13: avisa al Productor y al Veterinario, por correo y en la bandeja interna, que el
        período de retiro concluyó. Sin veterinario registrado en el tratamiento, el aviso interno va a los
        veterinarios de la finca del activo."""
        raise NotImplementedError

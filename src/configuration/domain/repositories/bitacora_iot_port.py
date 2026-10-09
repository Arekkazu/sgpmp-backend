"""Puerto (ABC) para auditar la emisión y revocación de credenciales MQTT (TC-M09-250/251).

La bitácora es ``modulo3.bitacora_auditoria_iot`` (RF-63), de otro módulo: el
adaptador la alcanza sin que el caso de uso la conozca. No se audita en
``modulo9.auditorias_dispositivos_iot`` porque su CHECK de ``tipo_operacion``
solo admite CREATE/DEACTIVATE/GET y ampliarlo exigiría una migración.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BitacoraIotPort(ABC):
    """Puerto hacia la bitácora IoT de M03 para auditar credenciales MQTT."""

    @abstractmethod
    def registrar(
        self,
        *,
        evento: str,
        exitoso: bool,
        id_dispositivo_iot: int,
        serial: str,
        id_usuario: int,
        detalle: dict,
    ) -> None:
        """Best-effort: nunca lanza. ``detalle`` jamás debe incluir la contraseña."""
        ...

"""Estado de una regla compuesta en cada Gateway Edge (DEV-08, RF-55/RF-57).

Una regla compuesta (THI, síndrome respiratorio, riesgo hídrico...) se envía a
los Gateway Edge por el broker con ``origen: "regla_compuesta"`` (BRK-05). Cada
Gateway responde con un veredicto propio, que se guarda por nodo en
``modulo3.sincronizaciones_reglas_edge``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

#: El Gateway confirmó con ``ACK_REGLA``: evalúa la versión enviada.
ESTADO_APLICADA = "APLICADA"
#: El broker sabe que el Gateway está desconectado y no publicó; o no hubo
#: integración con el broker. El Gateway sigue con la versión anterior.
ESTADO_PENDIENTE = "PENDIENTE"
#: Se intentó y falló: broker caído, error HTTP o sin ``ACK_REGLA`` a tiempo.
ESTADO_NO_CONF = "NO_CONF"
#: El ambiente no tiene broker configurado (resultado del adaptador, no de BD):
#: no hubo intento, así que se persiste como ``PENDIENTE``.
ESTADO_SIN_INTEGRACION = "SIN_INTEGRACION"

ESTADOS_SINCRONIZACION = (ESTADO_APLICADA, ESTADO_PENDIENTE, ESTADO_NO_CONF)


@dataclass(frozen=True)
class GatewayEdge:
    id_dispositivo_iot: int
    serial: str


@dataclass(frozen=True)
class ResultadoPropagacionEdge:
    """Veredicto del broker para un Gateway Edge."""

    estado: str
    mensaje: str
    # Si el broker llegó a publicar el comando en MQTT (devolvió el topic).
    publicado: Optional[bool] = None

    def estado_persistible(self) -> str:
        """El estado que se guarda en BD: solo los tres del ENUM."""
        if self.estado in ESTADOS_SINCRONIZACION:
            return self.estado
        if self.estado == ESTADO_SIN_INTEGRACION:
            return ESTADO_PENDIENTE
        # Un estado que el broker no documenta no confirma nada.
        return ESTADO_NO_CONF


@dataclass
class SincronizacionReglaEdge:
    id_regla_alertas: int
    id_dispositivo_iot: int
    serial: str
    version_regla: int
    estado_sincronizacion: str
    intentos_sincronizacion: int
    fecha_ultimo_intento: datetime
    mensaje: Optional[str] = None
    fecha_aplicacion: Optional[datetime] = None
    id_usuario: Optional[int] = None


@dataclass
class ResultadoSincronizacionRegla:
    """Resultado de propagar una regla: un estado consolidado y el de cada nodo."""

    id_regla_alertas: int
    version_regla: int
    estado: str
    mensaje: str
    nodos: list[SincronizacionReglaEdge] = field(default_factory=list)

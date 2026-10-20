"""Sincronización de la configuración del motor con los nodos Edge (DEV-09, RF-65).

Al guardar la configuración de un ``tipo_modelo`` se envía a cada Gateway Edge
que atiende un área con ese modelo asignado, por el broker con
``origen: "config_motor"`` (BRK-05, ``tipo_comando = CONFIG_MOTOR_IA``). El nodo
confirma con ``ACK_CONFIG_MOTOR`` y el ``config_version`` que quedó activo. El
veredicto se guarda en ``modulo4.sincronizacion_nodos_edge``:

| Respuesta del broker                 | estado_sincronizacion | HTTP      |
|--------------------------------------|-----------------------|-----------|
| APLICADA con el mismo config_version | APLICADA              | 201 / 200 |
| APLICADA con otro config_version     | DESINCRONIZADO        | 409 (E10) |
| PENDIENTE                            | PENDIENTE             | 202 (E7)  |
| NO_CONF                              | FALLIDA               | 202 (E8)  |
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

ESTADO_APLICADA = "APLICADA"
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_FALLIDA = "FALLIDA"
ESTADO_DESINCRONIZADO = "DESINCRONIZADO"

# Veredictos del broker (``CommandResponse.estado``) y del adaptador.
BROKER_APLICADA = "APLICADA"
BROKER_PENDIENTE = "PENDIENTE"
BROKER_NO_CONF = "NO_CONF"
#: El ambiente no tiene broker configurado: no hubo intento.
SIN_INTEGRACION = "SIN_INTEGRACION"


@dataclass(frozen=True)
class NodoEdge:
    id_dispositivo_iot: int
    serial: str


@dataclass(frozen=True)
class ResultadoEnvioConfigMotor:
    """Veredicto del broker para un nodo."""

    estado: str
    mensaje: str
    # El config_version que el nodo informó en su ACK_CONFIG_MOTOR (None si no lo trajo).
    config_version: Optional[int] = None
    publicado: Optional[bool] = None

    def estado_sincronizacion(self, config_version_servidor: int) -> str:
        """Traduce el veredicto del broker al estado de ``sincronizacion_nodos_edge``."""
        if self.estado == BROKER_APLICADA:
            # RF-65 E10: el nodo confirmó, pero quedó con otra versión.
            if self.config_version is not None and self.config_version != config_version_servidor:
                return ESTADO_DESINCRONIZADO
            return ESTADO_APLICADA
        if self.estado in (BROKER_PENDIENTE, SIN_INTEGRACION):
            return ESTADO_PENDIENTE
        # NO_CONF o cualquier estado que el broker no documenta.
        return ESTADO_FALLIDA


@dataclass
class SincronizacionNodoEdge:
    id_dispositivo_iot: int
    serial: str
    tipo_modelo: str
    config_version_servidor: int
    estado_sincronizacion: str
    intentos_sincronizacion: int
    config_version_nodo: Optional[int] = None
    fecha_ultimo_intento: Optional[datetime] = None
    fecha_aplicacion: Optional[datetime] = None
    motivo_fallo: Optional[str] = None


@dataclass
class ResultadoSincronizacionMotor:
    """Estado consolidado de la configuración en sus nodos."""

    estado: str
    mensaje: str
    nodos: list[SincronizacionNodoEdge] = field(default_factory=list)

    @property
    def hay_desincronizados(self) -> bool:
        return any(n.estado_sincronizacion == ESTADO_DESINCRONIZADO for n in self.nodos)

    @property
    def hay_sin_confirmar(self) -> bool:
        return any(n.estado_sincronizacion in (ESTADO_PENDIENTE, ESTADO_FALLIDA) for n in self.nodos)


def consolidar(nodos: list[SincronizacionNodoEdge]) -> ResultadoSincronizacionMotor:
    if not nodos:
        return ResultadoSincronizacionMotor(
            estado=ESTADO_APLICADA, mensaje="Ningún nodo Edge atiende este tipo de modelo.", nodos=[]
        )
    for estado in (ESTADO_DESINCRONIZADO, ESTADO_FALLIDA, ESTADO_PENDIENTE):
        afectados = [n for n in nodos if n.estado_sincronizacion == estado]
        if afectados:
            detalle = " | ".join(f"{n.serial}: {n.motivo_fallo}" for n in afectados)
            return ResultadoSincronizacionMotor(estado=estado, mensaje=detalle, nodos=nodos)
    return ResultadoSincronizacionMotor(
        estado=ESTADO_APLICADA, mensaje=f"Confirmada por {len(nodos)} nodo(s) Edge.", nodos=nodos
    )

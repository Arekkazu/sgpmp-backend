"""Schemas de respuesta de la credencial MQTT del Gateway Edge (RF-23, TC-M09-250/251)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.configuration.domain.repositories.mqtt_port import CredencialMqtt, EstadoCredencialMqtt


class CredencialMqttResponse(BaseModel):
    """La contraseña se muestra una sola vez: no se guarda en ningún lado."""

    usuario: str
    password: str
    seriales: list[str]

    @classmethod
    def from_entity(cls, credencial: CredencialMqtt) -> CredencialMqttResponse:
        return cls(usuario=credencial.usuario, password=credencial.password, seriales=credencial.seriales)


class EstadoCredencialMqttResponse(BaseModel):
    """Estado de la credencial MQTT en el broker; nunca incluye la clave."""
    # emitida=False: el dispositivo no tiene credencial propia (usa la compartida
    # o se comunica a través de su Gateway Edge).
    emitida: bool
    habilitada: bool = Field(default=False, description="La credencial está activa en el broker (no revocada).")
    conectada: bool = Field(
        default=False,
        description=(
            "El broker tiene una sesión MQTT viva de este usuario y el Edge no avisó su "
            "desconexión (Last Will DESCONEXION). Un corte de red sin cierre tarda hasta "
            "1,5 × keepalive en reflejarse. No basta para RF-17/RF-23: el broker además "
            "exige estado_actual = ACTIVO (RF-60, GET /iot/dispositivos/{id}/estado); "
            "si no, el comando queda PENDIENTE sin publicarse."
        ),
    )
    usuario: Optional[str] = None
    seriales: list[str] = []

    @classmethod
    def from_entity(cls, estado: Optional[EstadoCredencialMqtt]) -> EstadoCredencialMqttResponse:
        if estado is None:
            return cls(emitida=False)
        return cls(
            emitida=True,
            habilitada=estado.habilitada,
            conectada=estado.conectada,
            usuario=estado.usuario,
            seriales=estado.seriales,
        )

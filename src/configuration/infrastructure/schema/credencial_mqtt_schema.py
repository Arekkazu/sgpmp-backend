"""Schemas de respuesta de la credencial MQTT por Raspberry (RF-23, TC-M09-250/251)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

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
    # emitida=False: el dispositivo no tiene credencial propia (usa la compartida
    # o transmite a través de otra Raspberry).
    emitida: bool
    habilitada: bool = False
    conectada: bool = False
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

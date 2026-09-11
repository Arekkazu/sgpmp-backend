"""Entidad de dominio ``ConfiguracionGlobal`` — parámetros operativos del sistema (RF-18).

Singleton activo: solo puede haber uno con es_activo=True en el sistema.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.frecuencia_muestreo import FrecuenciaMuestreo
from src.configuration.domain.value_objects.heartbeat import Heartbeat
from src.shared.errors import ValidationError


@dataclass(eq=False)
class ConfiguracionGlobal:
    frecuencia_muestreo: FrecuenciaMuestreo
    heartbeat: Heartbeat
    es_activo: bool
    id_usuario: int
    fecha_actualizacion: datetime
    id_configuracion_global: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        frecuencia_muestreo: FrecuenciaMuestreo,
        heartbeat: Heartbeat,
        id_usuario: int,
        fecha_actualizacion: datetime,
    ) -> ConfiguracionGlobal:
        cls._validar_coherencia(frecuencia_muestreo, heartbeat)
        return cls(
            frecuencia_muestreo=frecuencia_muestreo,
            heartbeat=heartbeat,
            id_usuario=id_usuario,
            fecha_actualizacion=fecha_actualizacion,
            es_activo=True,
        )

    def actualizar(
        self,
        *,
        frecuencia_muestreo: FrecuenciaMuestreo,
        heartbeat: Heartbeat,
        id_usuario: int,
        fecha_actualizacion: datetime,
    ) -> None:
        self._validar_coherencia(frecuencia_muestreo, heartbeat)
        self.frecuencia_muestreo = frecuencia_muestreo
        self.heartbeat = heartbeat
        self.id_usuario = id_usuario
        self.fecha_actualizacion = fecha_actualizacion

    @staticmethod
    def _validar_coherencia(frecuencia: FrecuenciaMuestreo, heartbeat: Heartbeat) -> None:
        if heartbeat.valor < frecuencia.valor:
            raise ValidationError(
                code="HEARTBEAT_MENOR_FRECUENCIA",
                message=(
                    "Conflicto de lógica operativa: El tiempo de espera (heartbeat) debe ser "
                    "mayor o igual a la frecuencia de muestreo. No se puede esperar una señal "
                    "en un tiempo menor al intervalo de envío configurado."
                ),
                field="heartbeat",
            )

    def _snapshot(self) -> dict:
        return {
            "frecuencia_muestreo": self.frecuencia_muestreo.valor,
            "heartbeat": self.heartbeat.valor,
            "es_activo": self.es_activo,
            "id_usuario": self.id_usuario,
            "fecha_actualizacion": self.fecha_actualizacion.isoformat(),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfiguracionGlobal):
            return NotImplemented
        if self.id_configuracion_global is None or other.id_configuracion_global is None:
            return self is other
        return self.id_configuracion_global == other.id_configuracion_global

    def __hash__(self) -> int:
        return hash(self.id_configuracion_global)

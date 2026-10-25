# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTOs del orquestador OTA (DEV-15, D6 de AIOT-DEV-03)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import Field, field_validator, model_validator

from src.prediction.domain.entities.distribucion_ota import (
    PORCENTAJE_PARCIAL_DEFAULT,
    PORCENTAJE_PARCIAL_MAX,
    PORCENTAJE_PARCIAL_MIN,
)
from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc

EventoOtaNodo = Literal["status", "download_progress", "integrity_ok", "activated", "rollback", "critical_failure"]


class CrearDistribucionOtaDTO(BaseDTO):
    """``POST /prediccion/ota/distribuciones``. El orden de ``lista_dispositivos_objetivo``
    decide el rollout: el primero es el canary."""

    id_version_modelo: int = Field(gt=0)
    lista_dispositivos_objetivo: list[int] = Field(min_length=1)
    modo_distribucion: Literal["INMEDIATO", "PROGRAMADO", "POR_LOTES"]
    ventana_inicio: Optional[FechaHoraUtc] = None
    ventana_fin: Optional[FechaHoraUtc] = None
    nivel_bateria_minimo: Optional[Decimal] = Field(default=None, ge=0, le=100)
    tamano_fragmento_bytes: int = Field(gt=0)
    max_reintentos_descarga: int = Field(ge=0, le=20)
    porcentaje_parcial: int = Field(
        default=PORCENTAJE_PARCIAL_DEFAULT, ge=PORCENTAJE_PARCIAL_MIN, le=PORCENTAJE_PARCIAL_MAX,
        description="Porcentaje de nodos de la fase parcial del rollout (20–30 %).",
    )

    @field_validator("lista_dispositivos_objetivo")
    @classmethod
    def _sin_repetidos(cls, ids: list[int]) -> list[int]:
        if len(set(ids)) != len(ids):
            raise ValueError("lista_dispositivos_objetivo tiene dispositivos repetidos.")
        if any(i <= 0 for i in ids):
            raise ValueError("lista_dispositivos_objetivo solo admite ids positivos.")
        return ids

    @model_validator(mode="after")
    def _ventana_coherente(self) -> "CrearDistribucionOtaDTO":
        if self.modo_distribucion == "PROGRAMADO" and (self.ventana_inicio is None or self.ventana_fin is None):
            raise ValueError("El modo PROGRAMADO exige ventana_inicio y ventana_fin.")
        if self.ventana_inicio and self.ventana_fin and self.ventana_fin <= self.ventana_inicio:
            raise ValueError("ventana_fin debe ser posterior a ventana_inicio.")
        return self


class ReporteOtaDTO(BaseDTO):
    """``POST /prediccion/ota/reportes``: lo que el broker reenvía de ``ota/<evento>`` (BRK-08).

    ``serial`` es el del topic MQTT, ya autenticado por la ACL del broker.
    """

    serial: str = Field(min_length=1, max_length=100)
    id_despliegue_ota: int = Field(gt=0)
    componente: Optional[str] = None
    evento: EventoOtaNodo
    detalle: dict[str, Any] = Field(default_factory=dict)

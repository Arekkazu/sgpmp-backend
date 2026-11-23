# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: calidad de visión pendiente y evaluada |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, schemas y métodos |
"""Schemas de respuesta de la ingesta y de la calidad de visión (RF-62).

Cubre la telemetría aceptada, el resultado por lote y las observaciones de
visión con su evaluación de calidad (pendiente o calculada).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class TelemetriaResponse(BaseModel):
    """Identificador y estado de una lectura aceptada."""

    id_telemetria: int
    estado_calidad: str
    timestamp_procesamiento: datetime
    latencia_procesamiento_ms: Optional[int] = None


class ItemBatchResponse(BaseModel):
    """Resultado de un ítem dentro de un lote de ingesta."""

    sensor_id: int
    timestamp_captura: datetime
    estado: str
    id_telemetria: Optional[int] = None
    error: Optional[str] = None


class IngestaBatchResponse(BaseModel):
    """Resumen de un lote de ingesta con el detalle por ítem."""

    total: int
    aceptados: int
    rechazados: int
    duplicados: int
    detalle: list[ItemBatchResponse]


class ObservacionVisionResponse(BaseModel):
    """Observación de visión con su calidad (puede estar aún pendiente)."""

    id_observacion_vision: int
    timestamp_captura: datetime
    # RF-62: la calidad se evalúa después de la ingesta; null mientras está pendiente.
    indice_calidad_vision: Decimal | None = None
    clasificacion_calidad: str | None = None
    apto_para_ia: bool | None = None
    confianza_baja: bool | None = None
    flags_detectados: dict | None = None
    fecha_evaluacion_calidad: datetime | None = None
    # RF-62 v2.0: siempre false para visión.
    apto_para_nic41: bool = False
    ventana_inicio: datetime | None = None
    ventana_fin: datetime | None = None
    version_cascada: dict[str, str] | None = None

    @classmethod
    def desde(cls, o) -> "ObservacionVisionResponse":
        """Construye la respuesta a partir de la entidad de observación de visión."""
        return cls(
            id_observacion_vision=o.id_observacion_vision,
            timestamp_captura=o.fecha_observacion,
            indice_calidad_vision=o.indice_calidad_vision,
            clasificacion_calidad=o.clasificacion_calidad.value if o.clasificacion_calidad else None,
            apto_para_ia=o.es_apto_para_ia,
            confianza_baja=o.es_confianza_baja,
            flags_detectados=o.flags_detectados,
            fecha_evaluacion_calidad=o.fecha_evaluacion_calidad,
            ventana_inicio=o.fecha_inicio_ventana,
            ventana_fin=o.fecha_observacion,
            version_cascada=o.version_cascada,
        )


class IngestaVisionResponse(BaseModel):
    """Resumen de un lote de ingesta de observaciones de visión."""

    total: int
    aceptadas: int
    duplicadas: int
    observaciones: list[ObservacionVisionResponse]

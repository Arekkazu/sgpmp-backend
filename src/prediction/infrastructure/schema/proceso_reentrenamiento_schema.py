# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: respuesta de procesos de reentrenamiento y cuerpo del PATCH del motor |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.prediction.domain.entities.proceso_reentrenamiento import FASES, ProcesoReentrenamiento


class FaseProcesoResponse(BaseModel):
    fase: int
    nombre: str
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    #: None = en curso; OK | FALLIDA | INTERRUMPIDA.
    resultado: Optional[str] = None


class ProcesoReentrenamientoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_proceso_reentrenamiento: UUID
    tipo_modelo: str
    id_activo_biologico: int
    identificador_activo: Optional[str] = None
    disparador: str
    modo_generacion: str
    estado: str
    fase_actual: int
    #: Las 7 fases en orden, con lo que se sabe de cada una.
    fases: list[FaseProcesoResponse]
    porcentaje_progreso: int
    porcentaje_cpu: Optional[Decimal] = None
    memoria_ram_mb: Optional[int] = None
    codigo_error: Optional[str] = None
    motivos: Optional[list[Any]] = None
    id_version_modelo_referencia: Optional[int] = None
    id_version_modelo_resultante: Optional[int] = None
    nombre_version_resultante: Optional[str] = None
    id_usuario_solicitante: Optional[int] = None
    fecha_solicitud: datetime
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    fecha_ultimo_latido: Optional[datetime] = None

    @classmethod
    def from_entity(cls, p: ProcesoReentrenamiento) -> "ProcesoReentrenamientoResponse":
        por_numero = {f.get("fase"): f for f in p.fases}
        fases = [FaseProcesoResponse(fase=n, nombre=nombre, **{k: por_numero.get(n, {}).get(k) for k in ("fecha_inicio", "fecha_fin", "resultado")})
                 for n, nombre in enumerate(FASES, start=1)]
        datos = {k: getattr(p, k) for k in cls.model_fields if k != "fases" and hasattr(p, k)}
        return cls(**datos, fases=fases)


class ListaProcesosReentrenamientoResponse(BaseModel):
    items: list[ProcesoReentrenamientoResponse]
    total: int
    pagina: int
    por_pagina: int


class ActualizarProcesoDTO(BaseModel):
    """PATCH del motor: latido (fase/progreso/recursos) o cierre (estado COMPLETADO / FALLIDO)."""
    fase: Optional[int] = Field(default=None, ge=1, le=7)
    progreso: Optional[int] = Field(default=None, ge=0, le=100)
    cpu: Optional[Decimal] = Field(default=None, ge=0, le=100)
    ram_mb: Optional[int] = Field(default=None, ge=0)
    estado: Optional[Literal["COMPLETADO", "FALLIDO"]] = None
    id_version_modelo: Optional[int] = Field(default=None, gt=0)
    codigo_error: Optional[str] = Field(default=None, max_length=60)
    motivos: Optional[list[Any]] = None
    metricas: Optional[dict[str, Any]] = None


class RetroalimentacionesMotorResponse(BaseModel):
    retroalimentaciones: list[dict[str, Any]]

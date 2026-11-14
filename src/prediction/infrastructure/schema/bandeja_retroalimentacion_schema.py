# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.bandeja_retroalimentacion import InferenciaPorEvaluar


class InferenciaPorEvaluarResponse(BaseModel):
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    identificador_activo: Optional[str] = None
    especie: Optional[str] = None
    nombre_finca: Optional[str] = None
    nombre_area: Optional[str] = None
    nivel_riesgo: int
    id_patologia: Optional[int] = None
    nombre_patologia: Optional[str] = None
    confianza_global: Decimal
    fecha_inferencia: datetime
    fecha_inicio_ventana: Optional[datetime] = None
    fecha_fin_ventana: Optional[datetime] = None
    tiene_alerta_generada: bool
    #: Resultado de un modelo en sombra (de prueba): no generó alerta.
    modo_sombra: bool
    #: PENDIENTE | EVALUADO | VENTANA_VENCIDA.
    estado_evaluacion: str
    #: Último día en que se puede registrar (ventana de M09 o ampliación del Administrador).
    fecha_limite: datetime
    numero_evaluaciones: int
    evaluada_por_mi: bool
    activo_en_baja: bool
    #: El usuario actual puede registrar su evaluación (además necesita retroalimentacion_clinica · Crear).
    puede_evaluar: bool

    @classmethod
    def from_entity(cls, i: InferenciaPorEvaluar) -> "InferenciaPorEvaluarResponse":
        return cls(**{k: getattr(i, k) for k in cls.model_fields if k != "puede_evaluar"},
                   puede_evaluar=i.puede_evaluar)


class IndicadoresBandejaResponse(BaseModel):
    pendientes: int
    evaluadas: int
    vencidas: int


class BandejaRetroalimentacionResponse(BaseModel):
    items: list[InferenciaPorEvaluarResponse]
    total: int
    pagina: int
    por_pagina: int
    ventana_dias: int
    #: Por estado, con los mismos filtros salvo el de estado.
    indicadores: IndicadoresBandejaResponse

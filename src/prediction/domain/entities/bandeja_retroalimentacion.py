# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
"""Bandeja de retroalimentación clínica (RF-72): qué inferencias puede evaluar el veterinario.

El motor emite una inferencia por animal cada pocos minutos, así que la bandeja no lista todas:
solo las que abren un episodio de riesgo moderado o alto (el nivel pasa a 2 o 3 respecto a la
inferencia anterior del mismo animal), las que generaron alerta y cualquiera que ya tenga una
evaluación. El estado usa la misma ventana que el registro (``ventana_retroalimentacion_dias`` y
las ampliaciones por resultado del Administrador).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

ESTADOS_EVALUACION = ("PENDIENTE", "EVALUADO", "VENTANA_VENCIDA")


@dataclass(frozen=True)
class FiltrosBandejaRetroalimentacion:
    ids_fincas: Optional[list[int]]
    desde: datetime
    hasta: datetime
    ahora: datetime
    ventana_dias: int
    id_usuario: int
    estado_evaluacion: Optional[str] = None
    nivel_riesgo: Optional[int] = None
    id_activo_biologico: Optional[int] = None
    pagina: int = 1
    por_pagina: int = 25


@dataclass(frozen=True)
class InferenciaPorEvaluar:
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    identificador_activo: Optional[str]
    especie: Optional[str]
    nombre_finca: Optional[str]
    nombre_area: Optional[str]
    nivel_riesgo: int
    id_patologia: Optional[int]
    nombre_patologia: Optional[str]
    confianza_global: Decimal
    fecha_inferencia: datetime
    fecha_inicio_ventana: Optional[datetime]
    fecha_fin_ventana: Optional[datetime]
    tiene_alerta_generada: bool
    modo_sombra: bool
    estado_evaluacion: str
    en_ventana: bool
    fecha_limite: datetime
    numero_evaluaciones: int
    evaluada_por_mi: bool
    activo_en_baja: bool

    @property
    def puede_evaluar(self) -> bool:
        """Lo mismo que exige el registro: dentro de la ventana (o ampliada), sin una evaluación
        propia (una por veterinario y resultado) y con el activo fuera de BAJA."""
        return self.en_ventana and not self.evaluada_por_mi and not self.activo_en_baja


@dataclass(frozen=True)
class IndicadoresBandejaRetroalimentacion:
    pendientes: int = 0
    evaluadas: int = 0
    vencidas: int = 0

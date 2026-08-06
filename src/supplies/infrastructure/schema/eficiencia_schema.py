"""Schemas de respuesta del CU-02 — Eficiencia Alimenticia (ICA, RF-74)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA
from src.supplies.domain.entities.fallo_calculo_ica import FalloCalculoICA
from src.supplies.domain.entities.item_cola_ica import ItemColaICA
from src.supplies.domain.entities.resultado_ica import ResultadoICA


class ResultadoICAResponse(BaseModel):
    """Resultado de un cálculo ICA (vigente o histórico)."""

    id_resultado_ica: Optional[int]
    id_activo_biologico: int
    periodo_evaluacion: str
    fecha_inicio_periodo: datetime.date
    fecha_fin_periodo: datetime.date
    estado_resultado: str
    es_vigente: bool
    intento: int
    alimento_consumido_total_kg: Optional[Decimal]
    ganancia_peso_kg: Optional[Decimal]
    ca_calculado: Optional[Decimal]
    clasificacion_ca: Optional[str]
    data_quality_score: int
    causa_no_calculo: Optional[str]
    tipo_calculo: str
    id_usuario: Optional[int]
    fecha_calculo: Optional[datetime.datetime]

    @classmethod
    def desde_entidad(cls, r: ResultadoICA) -> "ResultadoICAResponse":
        return cls(
            id_resultado_ica=r.id_resultado_ica,
            id_activo_biologico=r.id_activo_biologico,
            periodo_evaluacion=r.periodo_evaluacion.value,
            fecha_inicio_periodo=r.fecha_inicio_periodo,
            fecha_fin_periodo=r.fecha_fin_periodo,
            estado_resultado=r.estado_resultado.value,
            es_vigente=r.es_vigente,
            intento=r.intento,
            alimento_consumido_total_kg=r.alimento_consumido_total_kg,
            ganancia_peso_kg=r.ganancia_peso_kg,
            ca_calculado=r.ca_calculado,
            clasificacion_ca=r.clasificacion_ca.value if r.clasificacion_ca else None,
            data_quality_score=r.data_quality_score,
            causa_no_calculo=r.causa_no_calculo.value if r.causa_no_calculo else None,
            tipo_calculo=r.tipo_calculo.value,
            id_usuario=r.id_usuario,
            fecha_calculo=r.fecha_calculo,
        )


class ConsultaVigenteResponse(BaseModel):
    """Vigente por (activo, período). ``resultado`` es ``None`` si no hay cálculo (FA-03)."""

    id_activo_biologico: int
    periodo_evaluacion: str
    tiene_resultado: bool
    mensaje: Optional[str]
    resultado: Optional[ResultadoICAResponse]


class HistorialICAResponse(BaseModel):
    """Historial de resultados ICA de un activo."""

    id_activo_biologico: int
    total: int
    items: list[ResultadoICAResponse]


class EstadoBatchResponse(BaseModel):
    """Estado y métricas de una corrida del batch ICA."""

    id_ejecucion: Optional[int]
    estado: str
    tipo_disparo: str
    hora_inicio: datetime.datetime
    hora_fin: Optional[datetime.datetime]
    hora_corte: Optional[datetime.datetime]
    cantidad_activos_total: int
    cantidad_activos_procesados: int
    cantidad_activos_pendientes: int
    cantidad_fallidos: int
    causa_interrupcion: Optional[str]
    num_workers: int
    limite_configurado: Optional[int]

    @classmethod
    def desde_entidad(cls, e: EjecucionBatchICA) -> "EstadoBatchResponse":
        return cls(
            id_ejecucion=e.id_ejecucion,
            estado=e.estado.value,
            tipo_disparo=e.tipo_disparo,
            hora_inicio=e.hora_inicio,
            hora_fin=e.hora_fin,
            hora_corte=e.hora_corte,
            cantidad_activos_total=e.cantidad_activos_total,
            cantidad_activos_procesados=e.cantidad_activos_procesados,
            cantidad_activos_pendientes=e.cantidad_activos_pendientes,
            cantidad_fallidos=e.cantidad_fallidos,
            causa_interrupcion=e.causa_interrupcion,
            num_workers=e.num_workers,
            limite_configurado=e.limite_configurado,
        )


class ItemColaResponse(BaseModel):
    id_cola: Optional[int]
    id_activo_biologico: int
    prioridad: int
    estado: str
    motivo: Optional[str]
    fecha_encolado: Optional[datetime.datetime]

    @classmethod
    def desde_entidad(cls, i: ItemColaICA) -> "ItemColaResponse":
        return cls(
            id_cola=i.id_cola,
            id_activo_biologico=i.id_activo_biologico,
            prioridad=i.prioridad,
            estado=i.estado.value,
            motivo=i.motivo,
            fecha_encolado=i.fecha_encolado,
        )


class ColaICAResponse(BaseModel):
    total: int
    items: list[ItemColaResponse]


class FalloICAResponse(BaseModel):
    id_fallo: Optional[int]
    id_activo_biologico: int
    periodo_evaluacion: Optional[str]
    causa_fallo: str
    intentos: int
    resuelto: bool
    timestamp_ultimo_intento: Optional[datetime.datetime]

    @classmethod
    def desde_entidad(cls, f: FalloCalculoICA) -> "FalloICAResponse":
        return cls(
            id_fallo=f.id_fallo,
            id_activo_biologico=f.id_activo_biologico,
            periodo_evaluacion=f.periodo_evaluacion.value if f.periodo_evaluacion else None,
            causa_fallo=f.causa_fallo,
            intentos=f.intentos,
            resuelto=f.resuelto,
            timestamp_ultimo_intento=f.timestamp_ultimo_intento,
        )


class FallosICAResponse(BaseModel):
    total: int
    items: list[FalloICAResponse]


class MensajeAccionResponse(BaseModel):
    """Respuesta genérica de una acción del panel batch (interrumpir/reactivar/reintentar)."""

    mensaje: str
    id_ejecucion: Optional[int] = None
    detalle: Optional[dict] = None

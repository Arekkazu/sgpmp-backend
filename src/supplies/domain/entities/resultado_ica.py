"""Entidad de dominio :class:`ResultadoICA` (RF-74 / CU-02).

Representa el resultado del cálculo del ICA de un activo en un período. Es pura
(sin ORM). Se construye a partir del resultado del servicio de dominio
(:class:`ResultadoCalculoICA`) con :meth:`desde_calculo`. Implementa ``_snapshot()``
para trazabilidad (el patrón de auditoría del proyecto).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.supplies.domain.services.calculadora_ica import ResultadoCalculoICA
from src.supplies.domain.value_objects.eficiencia_enums import (
    CausaNoCalculo,
    ClasificacionCA,
    EstadoResultadoCA,
    PeriodoEvaluacion,
    TipoCalculo,
)
from src.supplies.domain.value_objects.periodo_calculo import PeriodoCalculo


@dataclass(eq=False)
class ResultadoICA:
    """Resultado ICA persistible de un activo para un período."""

    id_activo_biologico: int
    periodo_evaluacion: PeriodoEvaluacion
    fecha_inicio_periodo: date
    fecha_fin_periodo: date
    estado_resultado: EstadoResultadoCA
    tipo_calculo: TipoCalculo
    data_quality_score: int
    es_vigente: bool = True
    intento: int = 1
    alimento_consumido_total_kg: Optional[Decimal] = None
    ganancia_peso_kg: Optional[Decimal] = None
    ca_calculado: Optional[Decimal] = None
    clasificacion_ca: Optional[ClasificacionCA] = None
    causa_no_calculo: Optional[CausaNoCalculo] = None
    id_usuario: Optional[int] = None
    id_resultado_ica: Optional[int] = None
    fecha_calculo: Optional[datetime] = None

    @classmethod
    def desde_calculo(
        cls,
        *,
        calculo: ResultadoCalculoICA,
        periodo: PeriodoCalculo,
        id_activo_biologico: int,
        tipo_calculo: TipoCalculo,
        intento: int = 1,
        id_usuario: Optional[int] = None,
    ) -> "ResultadoICA":
        return cls(
            id_activo_biologico=id_activo_biologico,
            periodo_evaluacion=periodo.periodo,
            fecha_inicio_periodo=periodo.fecha_inicio,
            fecha_fin_periodo=periodo.fecha_fin,
            estado_resultado=calculo.estado,
            tipo_calculo=tipo_calculo,
            data_quality_score=calculo.data_quality_score,
            alimento_consumido_total_kg=calculo.alimento_total_kg,
            ganancia_peso_kg=calculo.ganancia_peso_kg,
            ca_calculado=calculo.ca_calculado,
            clasificacion_ca=calculo.clasificacion_ca,
            causa_no_calculo=calculo.causa_no_calculo,
            intento=intento,
            id_usuario=id_usuario,
        )

    @property
    def es_critica(self) -> bool:
        return self.clasificacion_ca == ClasificacionCA.CRITICA

    def _snapshot(self) -> dict:
        return {
            "id_activo_biologico": self.id_activo_biologico,
            "periodo_evaluacion": self.periodo_evaluacion.value,
            "fecha_inicio_periodo": self.fecha_inicio_periodo.isoformat(),
            "fecha_fin_periodo": self.fecha_fin_periodo.isoformat(),
            "estado_resultado": self.estado_resultado.value,
            "ca_calculado": None if self.ca_calculado is None else str(self.ca_calculado),
            "clasificacion_ca": self.clasificacion_ca.value if self.clasificacion_ca else None,
            "causa_no_calculo": self.causa_no_calculo.value if self.causa_no_calculo else None,
            "data_quality_score": self.data_quality_score,
            "intento": self.intento,
            "tipo_calculo": self.tipo_calculo.value,
        }

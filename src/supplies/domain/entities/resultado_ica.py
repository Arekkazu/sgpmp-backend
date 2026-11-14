# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74: mensaje de cada flujo alterno      |
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
    # Solo del cálculo en curso (no se persisten): alimentan el mensaje de E4/E6.
    peso_inicial_kg: Optional[Decimal] = None
    peso_final_kg: Optional[Decimal] = None
    pesaje_descartado: Optional[tuple[date, Decimal]] = None

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
        peso_inicial_kg: Optional[Decimal] = None,
        peso_final_kg: Optional[Decimal] = None,
        pesaje_descartado: Optional[tuple[date, Decimal]] = None,
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
            peso_inicial_kg=peso_inicial_kg,
            peso_final_kg=peso_final_kg,
            pesaje_descartado=pesaje_descartado,
        )

    @property
    def mensaje(self) -> Optional[str]:
        """Causa legible de un CA_NO_CALCULABLE (RF-74 E2, E3, E4, E6); ``None`` si se calculó."""
        causa = self.causa_no_calculo
        if causa is None:
            return None
        if causa == CausaNoCalculo.SIN_REGISTROS_CONSUMO:
            return (
                "Sin registros de consumo de alimento validados en el período "
                f"{self.fecha_inicio_periodo.isoformat()} – {self.fecha_fin_periodo.isoformat()}."
            )
        if causa in (CausaNoCalculo.SIN_PESO_INICIAL, CausaNoCalculo.SIN_PESO_FINAL):
            return "No existen registros de pesaje inicial y final en el período evaluado."
        if causa == CausaNoCalculo.PESO_SIN_VARIACION_POSITIVA:
            pesos = (
                f" ({self.peso_inicial_kg} kg → {self.peso_final_kg} kg)"
                if self.peso_inicial_kg is not None and self.peso_final_kg is not None
                else ""
            )
            return f"La ganancia de peso en el período es cero o negativa{pesos}. El CA no es calculable."
        if causa == CausaNoCalculo.PESO_INVALIDO and self.pesaje_descartado is not None:
            fecha, valor = self.pesaje_descartado
            return (
                f"El registro de pesaje del {fecha.isoformat()} contiene un valor fuera del rango válido para "
                f"la especie ({valor} kg). Se descartó del cálculo."
            )
        if causa == CausaNoCalculo.PESO_INVALIDO:
            return "Los registros de pesaje del período tienen valores fuera del rango válido para la especie."
        return "Existen registros con valores corruptos o fuera de rango; el CA no es calculable."

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

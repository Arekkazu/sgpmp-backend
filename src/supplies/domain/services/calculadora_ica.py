"""Servicio de dominio: cálculo del Índice de Conversión Alimenticia (RF-74).

Corazón del CU-02. **Puro**: no toca BD, no lanza excepciones de flujo; recibe los
insumos ya recolectados (alimento total del período, peso inicial/final, tipo y
cantidad de la población) y devuelve un :class:`ResultadoCalculoICA` que es o bien
``CALCULADO`` (con CA y clasificación) o bien ``CA_NO_CALCULABLE`` (con la causa de
mayor precedencia y el ``data_quality_score``).

Fórmula (RF-74): ``CA = Alimento Total Consumido (kg) / Ganancia de Peso Total (kg)``.

- INDIVIDUAL: ``ganancia_total = peso_final - peso_inicial``.
- POBLACIONAL: los pesos son promedios por individuo (``nuevo_peso_promedio``); la
  ganancia total del lote es ``(peso_final - peso_inicial) * cantidad_actual``, de
  modo que se contrasta contra el alimento total del lote. No se convierten unidades
  (FA-09): se asume kg en ambos lados.

Umbrales de clasificación (por defecto del RF): ``<2.0`` EXCELENTE · ``2.0–3.5``
ACEPTABLE · ``3.5–5.0`` BAJA · ``>5.0`` CRITICA. ``CA`` se **trunca** a 4 decimales.
``data_quality_score = factores_presentes / 4 * 100`` (peso inicial, peso final,
consumo, variación positiva de peso).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Optional

from src.supplies.domain.value_objects.eficiencia_enums import (
    CausaNoCalculo,
    ClasificacionCA,
    EstadoResultadoCA,
)

_CUATRO_DECIMALES = Decimal("0.0001")

# Umbrales por defecto del RF-74.
_UMBRAL_EXCELENTE = Decimal("2.0")   # CA < 2.0
_UMBRAL_ACEPTABLE = Decimal("3.5")   # 2.0 <= CA <= 3.5
_UMBRAL_BAJA = Decimal("5.0")        # 3.5 < CA <= 5.0  (por encima → CRITICA)


@dataclass(frozen=True)
class ResultadoCalculoICA:
    """Resultado puro del cálculo del ICA para un activo y período."""

    estado: EstadoResultadoCA
    alimento_total_kg: Optional[Decimal]
    ganancia_peso_kg: Optional[Decimal]
    ca_calculado: Optional[Decimal]
    clasificacion_ca: Optional[ClasificacionCA]
    data_quality_score: int
    causa_no_calculo: Optional[CausaNoCalculo]

    @property
    def es_calculado(self) -> bool:
        return self.estado == EstadoResultadoCA.CALCULADO

    @property
    def es_critica(self) -> bool:
        return self.clasificacion_ca == ClasificacionCA.CRITICA


class CalculadoraICA:
    """Calcula el ICA de forma pura a partir de los insumos del período."""

    def calcular(
        self,
        *,
        alimento_total_kg: Optional[Decimal],
        peso_inicial_kg: Optional[Decimal],
        peso_final_kg: Optional[Decimal],
        es_poblacional: bool,
        cantidad_actual: Optional[int],
    ) -> ResultadoCalculoICA:
        score = self._data_quality_score(
            alimento_total_kg, peso_inicial_kg, peso_final_kg
        )

        causa = self._causa_no_calculable(
            alimento_total_kg=alimento_total_kg,
            peso_inicial_kg=peso_inicial_kg,
            peso_final_kg=peso_final_kg,
            es_poblacional=es_poblacional,
            cantidad_actual=cantidad_actual,
        )
        if causa is not None:
            return ResultadoCalculoICA(
                estado=EstadoResultadoCA.CA_NO_CALCULABLE,
                alimento_total_kg=alimento_total_kg,
                ganancia_peso_kg=self._ganancia_segura(peso_inicial_kg, peso_final_kg, es_poblacional, cantidad_actual),
                ca_calculado=None,
                clasificacion_ca=None,
                data_quality_score=score,
                causa_no_calculo=causa,
            )

        # Camino calculable — los insumos ya están validados por la jerarquía de causa.
        assert alimento_total_kg is not None and peso_inicial_kg is not None and peso_final_kg is not None
        ganancia = self._ganancia_total(peso_inicial_kg, peso_final_kg, es_poblacional, cantidad_actual)
        ca = (alimento_total_kg / ganancia).quantize(_CUATRO_DECIMALES, rounding=ROUND_DOWN)

        return ResultadoCalculoICA(
            estado=EstadoResultadoCA.CALCULADO,
            alimento_total_kg=alimento_total_kg,
            ganancia_peso_kg=ganancia,
            ca_calculado=ca,
            clasificacion_ca=self._clasificar(ca),
            data_quality_score=score,
            causa_no_calculo=None,
        )

    # ── Jerarquía de causa ───────────────────────────────────────────────────
    @staticmethod
    def _causa_no_calculable(
        *,
        alimento_total_kg: Optional[Decimal],
        peso_inicial_kg: Optional[Decimal],
        peso_final_kg: Optional[Decimal],
        es_poblacional: bool,
        cantidad_actual: Optional[int],
    ) -> Optional[CausaNoCalculo]:
        if peso_inicial_kg is None:
            return CausaNoCalculo.SIN_PESO_INICIAL
        if peso_final_kg is None:
            return CausaNoCalculo.SIN_PESO_FINAL
        if alimento_total_kg is None or alimento_total_kg <= 0:
            return CausaNoCalculo.SIN_REGISTROS_CONSUMO
        if es_poblacional and (cantidad_actual is None or cantidad_actual <= 0):
            return CausaNoCalculo.POBLACION_INVALIDA
        if peso_inicial_kg < 0 or peso_final_kg < 0:
            return CausaNoCalculo.PESO_INVALIDO
        if (peso_final_kg - peso_inicial_kg) <= 0:
            return CausaNoCalculo.PESO_SIN_VARIACION_POSITIVA
        return None

    # ── Auxiliares de cálculo ────────────────────────────────────────────────
    @staticmethod
    def _ganancia_total(
        peso_inicial_kg: Decimal, peso_final_kg: Decimal, es_poblacional: bool, cantidad_actual: Optional[int]
    ) -> Decimal:
        ganancia_individual = peso_final_kg - peso_inicial_kg
        if es_poblacional and cantidad_actual:
            return (ganancia_individual * Decimal(cantidad_actual)).quantize(_CUATRO_DECIMALES)
        return ganancia_individual.quantize(_CUATRO_DECIMALES)

    @classmethod
    def _ganancia_segura(
        cls,
        peso_inicial_kg: Optional[Decimal],
        peso_final_kg: Optional[Decimal],
        es_poblacional: bool,
        cantidad_actual: Optional[int],
    ) -> Optional[Decimal]:
        """Ganancia para persistir en un resultado no calculable (si hay ambos pesos)."""
        if peso_inicial_kg is None or peso_final_kg is None:
            return None
        return cls._ganancia_total(peso_inicial_kg, peso_final_kg, es_poblacional, cantidad_actual)

    @staticmethod
    def _clasificar(ca: Decimal) -> ClasificacionCA:
        if ca < _UMBRAL_EXCELENTE:
            return ClasificacionCA.EXCELENTE
        if ca <= _UMBRAL_ACEPTABLE:
            return ClasificacionCA.ACEPTABLE
        if ca <= _UMBRAL_BAJA:
            return ClasificacionCA.BAJA
        return ClasificacionCA.CRITICA

    @staticmethod
    def _data_quality_score(
        alimento_total_kg: Optional[Decimal],
        peso_inicial_kg: Optional[Decimal],
        peso_final_kg: Optional[Decimal],
    ) -> int:
        factores = [
            peso_inicial_kg is not None,
            peso_final_kg is not None,
            alimento_total_kg is not None and alimento_total_kg > 0,
            (
                peso_inicial_kg is not None
                and peso_final_kg is not None
                and (peso_final_kg - peso_inicial_kg) > 0
            ),
        ]
        return round(sum(1 for f in factores if f) / len(factores) * 100)

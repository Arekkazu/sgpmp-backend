"""Entidades del reporte de gastos acumulados (RF-77 / CU-04).

Python puro, sin SQLAlchemy ni FastAPI. ``ReporteGasto`` es el agregado de
salida del caso de uso; ``FiltrosReporteGasto`` modela los parámetros de
entrada ya validados. El cálculo (desglose, tendencia, promedio por individuo)
lo hace el use case — estas clases solo transportan datos y las reglas de
consistencia que les son propias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.supplies.domain.value_objects.reporte_gasto_enums import EstadoTendencia, GranularidadDesglose


@dataclass(frozen=True)
class FiltrosReporteGasto:
    """Parámetros validados de generación del reporte (RF-77)."""

    fecha_inicio: date
    fecha_fin: date
    tipo_periodo: str = GranularidadDesglose.CICLO_COMPLETO.value
    id_activo_biologico: Optional[int] = None
    id_infraestructura: Optional[int] = None
    id_especie: Optional[int] = None
    categorias_incluidas: Optional[list[str]] = None  # None = ALIMENTACION + MEDICACION

    @property
    def es_agregado(self) -> bool:
        """True si el reporte es por infraestructura/especie en vez de un activo puntual."""
        return self.id_activo_biologico is None

    @property
    def dias(self) -> int:
        return (self.fecha_fin - self.fecha_inicio).days + 1


@dataclass(frozen=True)
class LineaGasto:
    """Read-model de una línea de gasto (fuente: RF-75/RF-76 VALIDADO)."""

    categoria: str  # ALIMENTACION | MEDICACION
    id_origen: int
    id_activo_biologico: int
    id_infraestructura: Optional[int]
    id_especie: Optional[int]
    fecha: date
    descripcion: str
    cantidad: Decimal
    costo_unitario: Optional[Decimal]
    monto: Optional[Decimal]  # None => SIN_COSTO_REGISTRADO, excluido de los cálculos monetarios
    estado: str


@dataclass
class DesgloseCategoria:
    categoria: str
    subtotal: Decimal
    num_registros: int
    porcentaje: Decimal


@dataclass
class DesglosePeriodo:
    etiqueta: str  # "2026-05" (MENSUAL) o "2026-W18" (SEMANAL)
    fecha_inicio: date
    fecha_fin: date
    monto: Decimal


@dataclass
class TendenciaGasto:
    gasto_periodo_actual: Decimal
    gasto_periodo_anterior: Optional[Decimal]
    variacion_porcentual: Optional[Decimal]
    estado: str  # EstadoTendencia
    nota: Optional[str] = None


@dataclass
class RegistroSinCosto:
    categoria: str
    id_origen: int
    fecha: date
    descripcion: str


@dataclass(eq=False)
class ReporteGasto:
    """Agregado de salida del reporte de gastos acumulados (RF-77)."""

    fecha_inicio: date
    fecha_fin: date
    tipo_periodo: str
    gasto_total_acumulado: Decimal
    desglose_categorias: list[DesgloseCategoria] = field(default_factory=list)
    desglose_temporal: list[DesglosePeriodo] = field(default_factory=list)
    registros_sin_costo: list[RegistroSinCosto] = field(default_factory=list)
    tendencia: Optional[TendenciaGasto] = None
    id_activo_biologico: Optional[int] = None
    id_infraestructura: Optional[int] = None
    id_especie: Optional[int] = None
    gasto_promedio_individuo: Optional[Decimal] = None
    causa_no_calculable_promedio: Optional[str] = None
    nota_bajas: Optional[str] = None
    sin_datos: bool = False
    id_reporte_gasto_acumulado: Optional[int] = None
    id_usuario: Optional[int] = None
    fecha_generacion: Optional[datetime] = None

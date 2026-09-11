"""Entidades del historial/trazabilidad de suministros (RF-81 / CU-04).

Python puro, sin SQLAlchemy ni FastAPI. Lee sobre ``registro_suministro``
(ledger poblado desde RF-75/76, ver Gap 1 de ``cu04_gaps_bd_rf77_rf81.md``).
Operación estrictamente de solo lectura.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.supplies.domain.value_objects.historial_suministro_enums import (
    OrigenPrecioFiltro,
    TipoSuministroFiltro,
)


@dataclass(frozen=True)
class FiltrosHistorialSuministro:
    """Parámetros validados de consulta del historial (RF-81)."""

    id_activo_biologico: int
    id_ciclo_productivo: Optional[int] = None
    fecha_inicio_filtro: Optional[date] = None
    fecha_fin_filtro: Optional[date] = None
    tipo_suministro_filtro: str = TipoSuministroFiltro.TODOS.value
    origen_precio_filtro: str = OrigenPrecioFiltro.TODOS.value
    costo_min: Optional[Decimal] = None
    costo_max: Optional[Decimal] = None
    pagina: int = 1
    registros_por_pagina: int = 50

    def combinacion_valida(self) -> bool:
        """Restricción 7 de RF-81: fechas y rango de costo coherentes."""
        if (
            self.fecha_inicio_filtro is not None
            and self.fecha_fin_filtro is not None
            and self.fecha_fin_filtro < self.fecha_inicio_filtro
        ):
            return False
        if self.costo_min is not None and self.costo_max is not None and self.costo_max < self.costo_min:
            return False
        return True


@dataclass
class LineaHistorialSuministro:
    """Un registro del historial, enriquecido con contexto M02 si estuvo disponible."""

    id_registro_suministro: str
    id_activo_biologico: int
    id_ciclo_productivo: int
    tipo_suministro: str  # ALIMENTO | MEDICAMENTO
    descripcion: str
    fecha_aplicacion: date
    cantidad: Decimal
    unidad_medida: str
    precio_unitario: Decimal
    costo_registro: Decimal
    origen_precio: str
    tipo_operacion: str
    observacion: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    nombre_activo: Optional[str] = None
    especie: Optional[str] = None
    nombre_ciclo: Optional[str] = None
    estado_ciclo: Optional[str] = None


@dataclass
class ResultadoHistorialSuministro:
    """Página filtrada + agregados sobre el conjunto completo (no solo la página)."""

    lineas: list[LineaHistorialSuministro] = field(default_factory=list)
    total_registros_filtrados: int = 0
    monto_total_filtrado: Decimal = Decimal("0")
    desglose_por_tipo_suministro: dict = field(default_factory=dict)
    desglose_por_ciclo: dict = field(default_factory=dict)


@dataclass
class ResumenConsultaHistorial:
    """Resumen expuesto al cliente junto a la página de resultados."""

    total_registros_filtrados: int
    monto_total_filtrado: Decimal
    desglose_por_tipo_suministro: dict
    desglose_por_ciclo: dict
    pagina_actual: int
    total_paginas: int
    datos_contexto_no_disponibles: bool
    datos_actualizados_hasta: datetime
    nivel_volumen: int

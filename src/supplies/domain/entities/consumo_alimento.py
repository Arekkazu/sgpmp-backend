"""Entidad de dominio ``ConsumoAlimento`` (RF-75).

Python puro, sin SQLAlchemy ni FastAPI. Representa un registro de consumo de
alimento por un activo biológico. El registro es inmutable una vez ``VALIDADO``:
solo puede transicionar a ``ANULADO`` con justificación.

Nota: ``costo_total`` lo calcula un trigger de la BD a partir del precio del
catálogo; aquí se conserva para exponerlo tras releer el registro persistido.
``consumo_por_individuo_kg`` lo calcula el caso de uso para activos POBLACIONAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from src.supplies.domain.value_objects.estado_registro import EstadoRegistro


@dataclass(eq=False)
class ConsumoAlimento:
    """Registro de consumo de alimento de un activo biológico."""

    id_activo_biologico: int
    id_tipo_alimento: int
    tipo_alimento: str
    tipo_unidad: str
    cantidad_suministrada: Decimal
    fecha_consumo: date
    id_usuario: int
    estado_registro: str = EstadoRegistro.VALIDADO.value
    id_consumo_alimeto: Optional[int] = None
    hora_suministro: Optional[time] = None
    costo_unitario: Optional[Decimal] = None
    costo_total: Optional[Decimal] = None
    consumo_por_individuo_kg: Optional[Decimal] = None
    observacion: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    justificacion_anulacion: Optional[str] = None
    fecha_hora_anulacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_activo_biologico: int,
        id_tipo_alimento: int,
        tipo_alimento: str,
        tipo_unidad: str,
        cantidad_suministrada: Decimal,
        fecha_consumo: date,
        id_usuario: int,
        hora_suministro: Optional[time] = None,
        costo_unitario: Optional[Decimal] = None,
        consumo_por_individuo_kg: Optional[Decimal] = None,
        observacion: Optional[str] = None,
    ) -> "ConsumoAlimento":
        """Construye un consumo nuevo en estado VALIDADO, aún sin persistir."""
        return cls(
            id_activo_biologico=id_activo_biologico,
            id_tipo_alimento=id_tipo_alimento,
            tipo_alimento=tipo_alimento,
            tipo_unidad=tipo_unidad,
            cantidad_suministrada=cantidad_suministrada,
            fecha_consumo=fecha_consumo,
            id_usuario=id_usuario,
            hora_suministro=hora_suministro,
            costo_unitario=costo_unitario,
            consumo_por_individuo_kg=consumo_por_individuo_kg,
            observacion=observacion,
            estado_registro=EstadoRegistro.VALIDADO.value,
        )

    def anular(self, justificacion: str, fecha_hora: datetime) -> None:
        """Transiciona el registro a ANULADO (solo mutación de estado)."""
        self.estado_registro = EstadoRegistro.ANULADO.value
        self.justificacion_anulacion = justificacion
        self.fecha_hora_anulacion = fecha_hora

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConsumoAlimento):
            return NotImplemented
        if self.id_consumo_alimeto is None or other.id_consumo_alimeto is None:
            return self is other
        return self.id_consumo_alimeto == other.id_consumo_alimeto

    def __hash__(self) -> int:
        return hash(self.id_consumo_alimeto)

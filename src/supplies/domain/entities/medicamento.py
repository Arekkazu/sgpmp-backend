"""Entidad de dominio ``Medicamento`` (RF-76).

Python puro. Representa la aplicación de un medicamento a un activo biológico.
Inmutable una vez ``VALIDADO``; solo transiciona a ``ANULADO`` con justificación.

``costo_total_medicamento`` lo calcula un trigger de la BD (``cantidad *
costo_unitario_medicamento``); se conserva aquí para exponerlo tras releer el
registro. ``fecha_fin_retiro`` y ``dosis_por_individuo`` los calcula el caso de
uso.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from src.supplies.domain.value_objects.estado_registro import EstadoRegistro


@dataclass(eq=False)
class Medicamento:
    """Registro de aplicación de medicamento a un activo biológico."""

    id_activo_biologico: int
    nombre_medicamento: str
    descripcion_clinica: str
    unidad_dosis: str
    cantidad: Decimal
    fecha_aplicacion: date
    costo_unitario_medicamento: Decimal
    motivo_aplicacion: str
    nombre_veterinario: str
    id_usuario: int
    via_aplicacion: Optional[str] = None
    estado_registro: str = EstadoRegistro.VALIDADO.value
    id_registro_medicamento: Optional[int] = None
    hora_aplicacion: Optional[time] = None
    periodo_retiro_dias: int = 0
    fecha_fin_retiro: Optional[date] = None
    dosis_por_individuo: Optional[Decimal] = None
    id_evento_sanitario: Optional[int] = None
    id_usuario_veterinario: Optional[int] = None
    lote_medicameto: Optional[str] = None
    fehca_vencimietno_lote: Optional[date] = None
    costo_total_medicamento: Optional[Decimal] = None
    fecha_registro: Optional[datetime] = None
    justificacion_anulacion: Optional[str] = None
    fecha_hora_anulacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_activo_biologico: int,
        nombre_medicamento: str,
        descripcion_clinica: str,
        unidad_dosis: str,
        cantidad: Decimal,
        fecha_aplicacion: date,
        costo_unitario_medicamento: Decimal,
        motivo_aplicacion: str,
        nombre_veterinario: str,
        id_usuario: int,
        via_aplicacion: str,
        hora_aplicacion: Optional[time] = None,
        periodo_retiro_dias: int = 0,
        fecha_fin_retiro: Optional[date] = None,
        dosis_por_individuo: Optional[Decimal] = None,
        id_evento_sanitario: Optional[int] = None,
        id_usuario_veterinario: Optional[int] = None,
        lote_medicameto: Optional[str] = None,
        fehca_vencimietno_lote: Optional[date] = None,
    ) -> "Medicamento":
        """Construye una aplicación de medicamento en estado VALIDADO, sin persistir."""
        return cls(
            id_activo_biologico=id_activo_biologico,
            nombre_medicamento=nombre_medicamento,
            descripcion_clinica=descripcion_clinica,
            unidad_dosis=unidad_dosis,
            cantidad=cantidad,
            fecha_aplicacion=fecha_aplicacion,
            costo_unitario_medicamento=costo_unitario_medicamento,
            motivo_aplicacion=motivo_aplicacion,
            nombre_veterinario=nombre_veterinario,
            id_usuario=id_usuario,
            via_aplicacion=via_aplicacion,
            hora_aplicacion=hora_aplicacion,
            periodo_retiro_dias=periodo_retiro_dias,
            fecha_fin_retiro=fecha_fin_retiro,
            dosis_por_individuo=dosis_por_individuo,
            id_evento_sanitario=id_evento_sanitario,
            id_usuario_veterinario=id_usuario_veterinario,
            lote_medicameto=lote_medicameto,
            fehca_vencimietno_lote=fehca_vencimietno_lote,
            estado_registro=EstadoRegistro.VALIDADO.value,
        )

    def anular(self, justificacion: str, fecha_hora: datetime) -> None:
        """Transiciona el registro a ANULADO (solo mutación de estado)."""
        self.estado_registro = EstadoRegistro.ANULADO.value
        self.justificacion_anulacion = justificacion
        self.fecha_hora_anulacion = fecha_hora

    @property
    def requiere_periodo_retiro(self) -> bool:
        return bool(self.periodo_retiro_dias and self.periodo_retiro_dias > 0)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Medicamento):
            return NotImplemented
        if self.id_registro_medicamento is None or other.id_registro_medicamento is None:
            return self is other
        return self.id_registro_medicamento == other.id_registro_medicamento

    def __hash__(self) -> int:
        return hash(self.id_registro_medicamento)

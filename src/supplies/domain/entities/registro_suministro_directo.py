"""Entidad de dominio ``RegistroSuministroDirecto`` (RF-78 — registro directo).

Python puro. Representa una fila de ``modulo5.registro_suministro`` insertada
directamente por la app para SERVICIO_VETERINARIO/INSEMINACION (o una
CORRECCION de cualquier tipo de suministro). A diferencia de ALIMENTO/
MEDICAMENTO (poblados por trigger desde RF-75/76, sin cálculo en Python), aquí
no hay ningún trigger ``BEFORE INSERT`` que calcule ``costo_registro`` — lo
calcula la entidad misma (Restricción 7 de RF-78: ``costo_registro = cantidad
× precio_unitario_resuelto``). Append-only: no existe mutación de campos de
negocio, solo construcción vía ``crear()``/``crear_correccion()``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass(eq=False)
class RegistroSuministroDirecto:
    """Registro de suministro directo (SERVICIO_VETERINARIO/INSEMINACION o corrección)."""

    id_activo_biologico: int
    id_ciclo_productivo: int
    id_gestion_fases: int
    tipo_suministro: str
    cantidad: Decimal
    unidad_medida: str
    precio_unitario_resuelto: Decimal
    costo_registro: Decimal
    origen_precio: str
    fecha_aplicacion: date
    naturaleza_costo: str
    id_idempotencia: UUID
    tipo_operacion: str = "REGISTRO"
    justificacion_precio: Optional[str] = None
    observacion: Optional[str] = None
    id_registro_original: Optional[UUID] = None
    motivo_correccion: Optional[str] = None
    id_registro_suministro: Optional[UUID] = None
    fecha_registro: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_activo_biologico: int,
        id_ciclo_productivo: int,
        id_gestion_fases: int,
        tipo_suministro: str,
        cantidad: Decimal,
        unidad_medida: str,
        precio_unitario_resuelto: Decimal,
        fecha_aplicacion: date,
        naturaleza_costo: str,
        id_idempotencia: UUID,
        justificacion_precio: Optional[str] = None,
        observacion: Optional[str] = None,
        origen_precio: str = "MANUAL",
    ) -> "RegistroSuministroDirecto":
        """Construye un registro nuevo (``tipo_operacion=REGISTRO``), sin persistir."""
        return cls(
            id_activo_biologico=id_activo_biologico,
            id_ciclo_productivo=id_ciclo_productivo,
            id_gestion_fases=id_gestion_fases,
            tipo_suministro=tipo_suministro,
            cantidad=cantidad,
            unidad_medida=unidad_medida,
            precio_unitario_resuelto=precio_unitario_resuelto,
            costo_registro=cantidad * precio_unitario_resuelto,
            origen_precio=origen_precio,
            fecha_aplicacion=fecha_aplicacion,
            naturaleza_costo=naturaleza_costo,
            id_idempotencia=id_idempotencia,
            tipo_operacion="REGISTRO",
            justificacion_precio=justificacion_precio,
            observacion=observacion,
        )

    @classmethod
    def crear_correccion(
        cls,
        *,
        original: "RegistroSuministroDirecto",
        cantidad_corregida: Decimal,
        precio_unitario_corregido: Decimal,
        motivo_correccion: str,
        id_idempotencia: UUID,
        origen_precio: str = "MANUAL",
        justificacion_precio: Optional[str] = None,
    ) -> "RegistroSuministroDirecto":
        """Construye un registro de ajuste (``tipo_operacion=CORRECCION``) referenciando el original.

        Hereda ``id_activo_biologico``/``id_ciclo_productivo``/``id_gestion_fases``/
        ``tipo_suministro``/``unidad_medida``/``naturaleza_costo`` del original —
        una corrección no puede cambiar la identidad del suministro que ajusta.
        """
        return cls(
            id_activo_biologico=original.id_activo_biologico,
            id_ciclo_productivo=original.id_ciclo_productivo,
            id_gestion_fases=original.id_gestion_fases,
            tipo_suministro=original.tipo_suministro,
            cantidad=cantidad_corregida,
            unidad_medida=original.unidad_medida,
            precio_unitario_resuelto=precio_unitario_corregido,
            costo_registro=cantidad_corregida * precio_unitario_corregido,
            origen_precio=origen_precio,
            fecha_aplicacion=original.fecha_aplicacion,
            naturaleza_costo=original.naturaleza_costo,
            id_idempotencia=id_idempotencia,
            tipo_operacion="CORRECCION",
            justificacion_precio=justificacion_precio,
            observacion=None,
            id_registro_original=original.id_registro_suministro,
            motivo_correccion=motivo_correccion,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RegistroSuministroDirecto):
            return NotImplemented
        if self.id_registro_suministro is None or other.id_registro_suministro is None:
            return self is other
        return self.id_registro_suministro == other.id_registro_suministro

    def __hash__(self) -> int:
        return hash(self.id_registro_suministro)

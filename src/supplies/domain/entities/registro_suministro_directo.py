# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: corrección aditiva y compensación  |
"""Entidad de dominio ``RegistroSuministroDirecto`` (RF-78 — registro directo).

Python puro. Representa una fila de ``modulo5.registro_suministro`` insertada
directamente por la app para SERVICIO_VETERINARIO/INSEMINACION (o una
CORRECCION de cualquier tipo de suministro). Una CORRECCION es un ajuste que
SUMA al acumulado (RF-78 R12/CA-8) y puede ser negativo (RNF-09): el acumulado
del ciclo es siempre Σ ``costo_registro`` de todas las filas (R7). A diferencia de ALIMENTO/
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
    id_registro_rf75: Optional[UUID] = None
    id_registro_rf76: Optional[UUID] = None

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

        Su ``costo_registro`` se suma al acumulado (RF-78 R12); un precio
        negativo produce un ajuste compensatorio (RNF-09).

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

    @classmethod
    def crear_compensacion(
        cls,
        *,
        original: "RegistroSuministroDirecto",
        costo_compensatorio: Decimal,
        motivo_correccion: str,
        id_idempotencia: UUID,
    ) -> "RegistroSuministroDirecto":
        """CORRECCION que neutraliza el costo vigente de un registro anulado (RF-75/76 → RF-78).

        El costo se fija exacto (``-costo vigente``); el precio unitario es el que
        lo explica sobre la misma cantidad, redondeado a 4 decimales.
        """
        correccion = cls.crear_correccion(
            original=original,
            cantidad_corregida=original.cantidad,
            precio_unitario_corregido=(costo_compensatorio / original.cantidad).quantize(Decimal("0.0001")),
            motivo_correccion=motivo_correccion,
            id_idempotencia=id_idempotencia,
            origen_precio=original.origen_precio,
        )
        correccion.costo_registro = costo_compensatorio
        return correccion

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RegistroSuministroDirecto):
            return NotImplemented
        if self.id_registro_suministro is None or other.id_registro_suministro is None:
            return self is other
        return self.id_registro_suministro == other.id_registro_suministro

    def __hash__(self) -> int:
        return hash(self.id_registro_suministro)
